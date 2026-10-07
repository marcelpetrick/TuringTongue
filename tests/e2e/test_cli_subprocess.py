# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""End-to-end: run the real ``python -m turingtongue`` entry point in a subprocess."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def run(*args: str, stdin: str = "", **env: str) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(Path.cwd()),
        "TURINGTONGUE_NO_DOTENV": "1",
        **env,
    }
    return subprocess.run(
        [sys.executable, "-m", "turingtongue", *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=60,
    )


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def test_default_mode_is_one_word() -> None:
    done = run("check", "-", "-p", "mock", stdin="Hello there.\n")
    assert (done.returncode, done.stdout) == (0, "HUMAN\n")


def test_ai_verdict_exit_zero() -> None:
    done = run("check", "--text", "x", "-p", "mock", TURINGTONGUE_MOCK_RESULT="ai")
    assert (done.returncode, done.stdout) == (0, "AI\n")


def test_all_providers_unconfigured_json() -> None:
    done = run("check", "--text", "Ein kurzer deutscher Text.", "-p", "all", "--json")
    assert done.returncode == 2
    data = json.loads(done.stdout)
    assert data["verdict"] == "no_verdict"
    assert {e["category"] for e in data["errors"]} == {"NOT_CONFIGURED"}
    assert len(data["errors"]) == len(data["selection"]["selected"])


def test_verbose_lists_unconfigured_and_skipped() -> None:
    done = run("check", "--text", "Some text.", "-v", "-p", "mock", "-p", "all")
    assert done.returncode == 0
    assert "not_configured" in done.stdout
    assert "Mock (offline)" in done.stdout


def test_default_selection_reports_skipped() -> None:
    done = run("check", "--text", "Some text.", "-v")
    assert done.returncode == 2
    assert "skipped — not configured" in done.stdout
    assert "No provider ran." in done.stdout


def test_bad_arguments_exit_3() -> None:
    assert run("check", "--transport", "smoke-signals").returncode == 3
