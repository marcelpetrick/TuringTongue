# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import csv
import io
from pathlib import Path

import pytest

from turingtongue import Checker, ConfigurationError, Settings
from turingtongue.batch import collect_files, front_matter_date, run_batch, write_csv

pytestmark = pytest.mark.unit


def test_collect_files(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.md").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    (tmp_path / "c.png").write_text("z")
    single = tmp_path / "c.png"
    assert collect_files([tmp_path]) == [tmp_path / "b.txt", tmp_path / "sub" / "a.md"]
    assert collect_files([single]) == [single]
    with pytest.raises(ConfigurationError, match="not a file"):
        collect_files([tmp_path / "missing"])
    with pytest.raises(ConfigurationError, match="no input files"):
        collect_files([tmp_path / "sub"], patterns=["*.rst"])


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("---\ntitle: x\ndate: 2019-04-01\n---\nBody", "2019-04-01"),
        ("---\ndate: '2018-01-02 10:00'\n---\n", "2018-01-02 10:00"),
        ("---\ntitle: x\n---\nBody", None),
        ("No front matter. date: 2020", None),
        ("---\nunterminated date: x", None),
    ],
)
def test_front_matter_date(text: str, date: str | None) -> None:
    assert front_matter_date(text) == date


async def test_run_batch_rows(tmp_path: Path) -> None:
    good = tmp_path / "post.md"
    good.write_text("---\ndate: 2019-04-01\n---\nA blog post body.", encoding="utf-8")
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe")
    empty = tmp_path / "empty.txt"
    empty.write_text("   ")
    seen = []
    rows = await run_batch(
        Checker(Settings(env={})),
        [good, bad, empty],
        providers=["mock"],
        on_result=lambda p, r, res: seen.append(p),
    )
    assert seen == [good]
    assert rows[0]["verdict"] == "HUMAN"
    assert rows[0]["date"] == "2019-04-01"
    assert rows[0]["providers_succeeded"] == 1
    assert rows[0]["model_versions"] == "mock=1"
    assert [r["verdict"] for r in rows[1:]] == ["SKIPPED", "SKIPPED"]
    out = io.StringIO()
    write_csv(rows, out)
    parsed = list(csv.DictReader(io.StringIO(out.getvalue())))
    assert parsed[0]["file"] == str(good)
    assert next(iter(parsed[0])) == "file"
