# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
from pathlib import Path

import pytest

from turingtongue.config import ProviderOverrides, Settings, read_dotenv
from turingtongue.credentials.store import save_dotenv_credential
from turingtongue.errors import ConfigurationError

pytestmark = pytest.mark.unit


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_without_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = Settings.load(env={}, dotenv_path=None)
    assert settings.timeout_s == 30.0
    assert settings.providers == {}
    assert settings.overrides("x") == ProviderOverrides()


def test_credential_lookup_blank_is_missing() -> None:
    settings = Settings(env={"A": " k ", "B": "  "})
    assert settings.credential("A") == "k"
    assert settings.credential("B") is None
    assert settings.credential("C") is None


def test_toml_values(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
[defaults]
timeout_s = 12
max_concurrency = 2

[providers.sapling]
enabled = false
weight = 0.5
timeout_s = 9
options = { model = "x" }
""",
    )
    settings = Settings.load(path, env={}, dotenv_path=None)
    assert settings.timeout_s == 12
    assert settings.max_concurrency == 2
    sapling = settings.overrides("sapling")
    assert (sapling.enabled, sapling.weight, sapling.timeout_s) == (False, 0.5, 9)
    assert sapling.options == {"model": "x"}


def test_config_path_from_env(tmp_path: Path) -> None:
    path = _write(tmp_path, "[defaults]\nmax_retries = 0\n")
    settings = Settings.load(env={"TURINGTONGUE_CONFIG": str(path)}, dotenv_path=None)
    assert settings.max_retries == 0


def test_default_config_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".config" / "turingtongue"
    cfg.mkdir(parents=True)
    (cfg / "config.toml").write_text("[defaults]\ntimeout_s = 3\n")
    assert Settings.load(env={}, dotenv_path=None).timeout_s == 3


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[defaults]\napi_key = 'x'\n", "looks like a secret"),
        ("[providers.gptzero]\ntoken = 'x'\n", "looks like a secret"),
        ("[defaults]\nbogus = 1\n", "unknown keys in \\[defaults\\]"),
        ("[providers.x]\nbogus = 1\n", "unknown keys in \\[providers.x\\]"),
        ("[other]\n", "unknown config sections"),
        ("[providers.x]\nweight = -1\n", "non-negative"),
        ("not = = toml", "cannot read config file"),
    ],
)
def test_invalid_config(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        Settings.load(_write(tmp_path, text), env={}, dotenv_path=None)


def test_missing_explicit_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        Settings.load(tmp_path / "nope.toml", env={}, dotenv_path=None)


def test_dotenv_does_not_override_environment(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# comment\nexport A='quoted value'\nB=plain # trailing\nC=from-file\nnoequals\n\n"
    )
    assert read_dotenv(dotenv) == {"A": "quoted value", "B": "plain", "C": "from-file"}
    settings = Settings.load(env={"C": "real"}, dotenv_path=dotenv)
    assert settings.credential("A") == "quoted value"
    assert settings.credential("C") == "real"


def test_dotenv_disabled_by_env(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("A=1\n")
    settings = Settings.load(env={"TURINGTONGUE_NO_DOTENV": "1"}, dotenv_path=dotenv)
    assert settings.credential("A") is None


def test_atomic_dotenv_credential_preserves_content_and_round_trips(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("KEEP=one\nZEROGPT_API_KEY=old\n", encoding="utf-8")
    save_dotenv_credential(dotenv, "ZEROGPT_API_KEY", 'new value with "quotes" and #')
    assert read_dotenv(dotenv) == {
        "KEEP": "one",
        "ZEROGPT_API_KEY": 'new value with "quotes" and #',
    }
    assert dotenv.stat().st_mode & 0o077 == 0


def test_atomic_dotenv_credential_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("KEEP=unchanged\n", encoding="utf-8")
    dotenv = tmp_path / ".env"
    dotenv.symlink_to(target)
    with pytest.raises(ConfigurationError, match="non-regular"):
        save_dotenv_credential(dotenv, "ZEROGPT_API_KEY", "secret")
    assert target.read_text(encoding="utf-8") == "KEEP=unchanged\n"


def test_with_changes() -> None:
    assert Settings(env={}).with_changes(timeout_s=1).timeout_s == 1
