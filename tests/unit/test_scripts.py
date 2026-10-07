# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
from pathlib import Path

import pytest

from scripts import bump_version, check_headers

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("part", "expected"),
    [("patch", (1, 2, 4)), ("minor", (1, 3, 0)), ("major", (2, 0, 0))],
)
def test_bumped(part: str, expected: tuple[int, int, int]) -> None:
    assert bump_version.bumped((1, 2, 3), part) == expected


def test_bumped_rejects_unknown_part() -> None:
    with pytest.raises(ValueError, match="unknown part"):
        bump_version.bumped((1, 2, 3), "tiny")


def test_read_and_apply_roundtrip() -> None:
    text = '[project]\nname = "x"\nversion = "0.4.9"\n[tool.x]\nversion = "9.9.9"\n'
    assert bump_version.read_version(text) == (0, 4, 9)
    updated = bump_version.apply(text, (0, 5, 0))
    assert 'version = "0.5.0"' in updated
    assert 'version = "9.9.9"' in updated


def test_read_version_requires_line() -> None:
    with pytest.raises(ValueError, match="no 'version"):
        bump_version.read_version("[project]\n")


def test_show_prints_current(capsys: pytest.CaptureFixture[str]) -> None:
    assert bump_version.main(["--show"]) == 0
    assert capsys.readouterr().out.count(".") == 2


def test_header_check_flags_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text(
        "# SPDX-License-Identifier: GPL-3.0-or-later\n# Copyright (C) 2026 X\n"
    )
    (tmp_path / "src" / "empty.py").write_text("")
    (tmp_path / "bad.sh").write_text("#!/bin/sh\necho hi\n")
    assert check_headers.main([str(tmp_path)]) == 1
    assert "bad.sh" in capsys.readouterr().out


def test_header_check_passes_on_repository() -> None:
    assert check_headers.main([]) == 0
