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


PLAN_SAMPLE = """## Phase

- [ ] T001 — First
  - Status: todo
  - Depends on: —
  - Acceptance:
    - [ ] a
    - [ ] b
  - Notes: —
- [ ] T002 — Second
  - Status: todo
  - Acceptance:
    - [ ] c
  - Notes: —

## Next
"""


def test_plan_task_done_ticks_only_target() -> None:
    from scripts import plan_task

    out = plan_task.update(PLAN_SAMPLE, "T001", "done", "shipped")
    first, second = out.split("- [ ] T002")
    assert "- [x] T001" in first
    assert "Status: done" in first
    assert first.count("    - [x]") == 2
    assert "Notes: shipped" in first
    assert "    - [ ] c" in second


def test_plan_task_unknown_id() -> None:
    from scripts import plan_task

    with pytest.raises(KeyError):
        plan_task.update(PLAN_SAMPLE, "T999", "done", None)


def test_plan_task_main(tmp_path: Path) -> None:
    from scripts import plan_task

    plan = tmp_path / "plan.md"
    plan.write_text(PLAN_SAMPLE)
    assert plan_task.main(["T002", "in_progress", "--plan", str(plan)]) == 0
    assert "Status: in_progress" in plan.read_text()


def test_bump_from_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.1"\n')
    monkeypatch.setattr(bump_version, "PYPROJECT", pyproject)
    assert bump_version.main(["minor", "--from-version", "0.1.0", "--no-lock"]) == 0
    assert 'version = "0.2.0"' in pyproject.read_text()
