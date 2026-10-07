# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import io
import json
from pathlib import Path

import pytest

from turingtongue.cli import main as cli
from turingtongue.cli.output import provider_label
from turingtongue.models import ProviderResult, ProviderStatus, TransportKind

pytestmark = pytest.mark.unit


class Streams:
    def __init__(self, stdin: bytes = b"") -> None:
        self.stdin = io.TextIOWrapper(io.BytesIO(stdin), encoding="utf-8")
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def run(self, *argv: str) -> int:
        return cli.run(list(argv), stdin=self.stdin, stdout=self.stdout, stderr=self.stderr)


@pytest.fixture(autouse=True)
def _no_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def test_default_output_is_one_line() -> None:
    s = Streams(b"Some text to check.")
    assert s.run("check", "-p", "mock") == cli.EXIT_VERDICT
    assert s.stdout.getvalue() == "HUMAN\n"


def test_ai_verdict_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TURINGTONGUE_MOCK_RESULT", "ai")
    s = Streams()
    assert s.run("check", "--text", "x y z", "--provider", "mock") == 0
    assert s.stdout.getvalue() == "AI\n"


def test_no_verdict_exit_code_without_providers() -> None:
    s = Streams()
    assert s.run("check", "--text", "hello") == cli.EXIT_NO_VERDICT
    assert s.stdout.getvalue() == "NO_VERDICT\n"


def test_json_output(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"line one\r\nline two  ")
    s = Streams()
    assert s.run("check", str(path), "--json", "-p", "mock,mock") == 0
    data = json.loads(s.stdout.getvalue())
    assert data["schema_version"] == "1.0"
    assert data["input"]["characters"] == len("line one\r\nline two  ")
    assert [p["provider_id"] for p in data["providers"]] == ["mock"]


def test_verbose_output(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Streams()
    code = s.run("check", "--text", "abc def", "-v", "-p", "mock", "-p", "all", "--timeout", "5")
    out = s.stdout.getvalue()
    assert code == 0
    for needle in (
        "Verdict: HUMAN",
        "Agreement:",
        "Wall clock:",
        "Mock (offline)",
        "weight factors",
        "Ensemble reasoning",
        "not proof of authorship",
    ):
        assert needle in out


def test_verbose_no_provider() -> None:
    s = Streams()
    assert s.run("check", "--text", "abc", "--verbose") == 2
    assert "No provider ran." in s.stdout.getvalue()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["check", "/does/not/exist"], "file not found"),
        (["check", "--text", "   "], "empty"),
        (["check", "--text", "a", "-p", "nope"], "unknown provider"),
        (["check", "--text", "a", "--timeout", "0"], "must be positive"),
        (["--config", "/nope.toml", "providers"], "config file not found"),
    ],
)
def test_usage_errors_exit_3(argv: list[str], message: str) -> None:
    s = Streams()
    assert s.run(*argv) == cli.EXIT_USAGE
    assert message in s.stderr.getvalue()


def test_argparse_errors_exit_3(capsys: pytest.CaptureFixture[str]) -> None:
    assert Streams().run("check", "--transport", "pigeon") == cli.EXIT_USAGE
    assert Streams().run() == cli.EXIT_USAGE


def test_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert Streams().run("--help") == 0
    assert "Privacy:" in capsys.readouterr().out
    assert Streams().run("--version") == 0
    assert "turingtongue" in capsys.readouterr().out


def test_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\xff\xfe\xfa")
    s = Streams()
    assert s.run("check", str(path)) == cli.EXIT_USAGE
    assert "UTF-8" in s.stderr.getvalue()


def test_unreadable_path(tmp_path: Path) -> None:
    s = Streams()
    assert s.run("check", str(tmp_path)) == cli.EXIT_USAGE


def test_stdin_without_buffer() -> None:
    assert cli.read_text("-", None, io.StringIO("plain")) == "plain"


def test_internal_error_exit_4(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("kaputt")

    monkeypatch.setattr("turingtongue.client.Checker.check", boom)
    s = Streams()
    assert s.run("--debug", "check", "--text", "x") == cli.EXIT_INTERNAL
    assert "kaputt" in s.stderr.getvalue()


def test_providers_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Streams()
    assert s.run("providers") == 0
    assert "mock" in s.stdout.getvalue()
    s = Streams()
    assert s.run("providers", "--json") == 0
    rows = json.loads(s.stdout.getvalue())
    assert {"id", "credentials_present", "credential_env"} <= rows[0].keys()


def test_provider_label() -> None:
    base = {
        "provider_id": "x",
        "provider_name": "x",
        "transport": TransportKind.API,
        "status": ProviderStatus.OK,
    }
    assert provider_label(ProviderResult(**base)) == "—"  # type: ignore[arg-type]
    assert provider_label(ProviderResult(**base, normalized_evidence=0.0)) == "MIXED"  # type: ignore[arg-type]
