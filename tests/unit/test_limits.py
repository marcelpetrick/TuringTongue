# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import pytest

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory
from turingtongue.normalization.limits import (
    LimitUnit,
    PreparedInput,
    exact_prefix,
    measure,
    prepare_input,
)

pytestmark = pytest.mark.unit

TEXT = "Ünïcödé  text\twith 👩‍💻 emoji\nand nbsp."  # noqa: RUF001 - deliberate exotic whitespace


def test_measure() -> None:
    assert measure(TEXT, LimitUnit.CHARACTERS) == len(TEXT)
    assert measure(TEXT, LimitUnit.UTF8_BYTES) == len(TEXT.encode())
    assert measure(TEXT, LimitUnit.WORDS) == len(TEXT.split())
    assert measure(TEXT, LimitUnit.TOKENS) is None


def test_full_text_is_untouched_when_it_fits() -> None:
    prepared = prepare_input(TEXT, max_size=10_000, min_size=None, unit=LimitUnit.CHARACTERS)
    assert prepared.text is TEXT
    assert not prepared.truncated
    assert prepared.coverage == 1.0


@pytest.mark.parametrize("limit", range(len(TEXT.encode()) + 1))
def test_byte_prefix_is_exact_and_valid(limit: int) -> None:
    prefix = exact_prefix(TEXT, limit, LimitUnit.UTF8_BYTES)
    assert TEXT.startswith(prefix)
    assert len(prefix.encode()) <= limit
    if len(prefix) < len(TEXT):
        assert len(TEXT[: len(prefix) + 1].encode()) > limit


def test_character_prefix() -> None:
    assert exact_prefix(TEXT, 3, LimitUnit.CHARACTERS) == "Ünï"


@pytest.mark.parametrize("words", [0, 1, 2, 3, 6, 99])
def test_word_prefix_preserves_whitespace(words: int) -> None:
    prefix = exact_prefix(TEXT, words, LimitUnit.WORDS)
    assert TEXT.startswith(prefix)
    assert len(prefix.split()) == min(words, len(TEXT.split()))
    if 0 < words < len(TEXT.split()):
        assert not prefix[-1].isspace()


def test_word_prefix_keeps_inner_double_space() -> None:
    assert exact_prefix(TEXT, 2, LimitUnit.WORDS) == "Ünïcödé  text"


def test_prefix_errors() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        exact_prefix("x", -1, LimitUnit.CHARACTERS)
    with pytest.raises(ValueError, match="token"):
        exact_prefix("x", 1, LimitUnit.TOKENS)


def test_truncation_reports_coverage() -> None:
    prepared = prepare_input("a b c d", max_size=2, min_size=None, unit=LimitUnit.WORDS)
    assert prepared == PreparedInput("a b", 7, 3, truncated=True)
    assert prepared.coverage == pytest.approx(3 / 7)


def test_too_short() -> None:
    with pytest.raises(ProviderFailure) as info:
        prepare_input("short", max_size=None, min_size=50, unit=LimitUnit.CHARACTERS)
    assert info.value.category is ErrorCategory.INPUT_TOO_SHORT


def test_token_limit_without_boundary() -> None:
    small = prepare_input("tiny", max_size=10, min_size=5, unit=LimitUnit.TOKENS)
    assert not small.truncated
    with pytest.raises(ProviderFailure) as info:
        prepare_input("x" * 20, max_size=10, min_size=None, unit=LimitUnit.TOKENS)
    assert info.value.category is ErrorCategory.INPUT_TOO_LARGE


def test_no_prefix_fits() -> None:
    with pytest.raises(ProviderFailure) as info:
        prepare_input("👋", max_size=1, min_size=None, unit=LimitUnit.UTF8_BYTES)
    assert info.value.category is ErrorCategory.INPUT_TOO_LARGE


def test_empty_text_coverage() -> None:
    assert PreparedInput("", 0, 0, truncated=False).coverage == 1.0
