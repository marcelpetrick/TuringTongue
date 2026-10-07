# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Deterministic, exact-prefix handling of provider input size limits (vision §6).

The caller's text is never rewritten. When a provider's documented *hard* limit is
exceeded we submit the largest exact prefix that fits — every retained character is
identical to the original — and report ``truncated`` plus coverage. When no safe
boundary can be determined (e.g. a provider-specific tokenizer) the provider is
skipped with ``INPUT_TOO_LARGE`` instead of guessing.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory

_WORD = re.compile(r"\S+")


class LimitUnit(enum.StrEnum):
    """Unit in which a provider documents its input limits."""

    CHARACTERS = "characters"
    """Unicode code points, i.e. ``len(str)`` in Python."""
    UTF8_BYTES = "utf8_bytes"
    WORDS = "words"
    """Whitespace-separated runs of non-whitespace characters."""
    TOKENS = "tokens"
    """Provider tokenizer units — cannot be measured locally."""


@dataclass(frozen=True, slots=True)
class PreparedInput:
    """What will be sent to one provider."""

    text: str
    input_characters: int
    submitted_characters: int
    truncated: bool

    @property
    def coverage(self) -> float:
        """Share of the caller's characters that the provider actually sees."""
        if self.input_characters == 0:
            return 1.0
        return self.submitted_characters / self.input_characters


def _utf8_len(text: str) -> int:
    return len(text.encode("utf-8", errors="surrogatepass"))


def measure(text: str, unit: LimitUnit) -> int | None:
    """Size of ``text`` in ``unit``; None when it cannot be measured locally."""
    match unit:
        case LimitUnit.CHARACTERS:
            return len(text)
        case LimitUnit.UTF8_BYTES:
            return _utf8_len(text)
        case LimitUnit.WORDS:
            return len(text.split())
        case LimitUnit.TOKENS:
            return None


def exact_prefix(text: str, limit: int, unit: LimitUnit) -> str:
    """Largest prefix of ``text`` whose size in ``unit`` is ``<= limit``.

    Cuts only on character boundaries (bytes) or at the end of a word (words); all
    characters before the boundary are preserved exactly.
    """
    if limit < 0:
        raise ValueError("limit must be >= 0")
    match unit:
        case LimitUnit.CHARACTERS:
            return text[:limit]
        case LimitUnit.UTF8_BYTES:
            used = 0
            for index, char in enumerate(text):
                used += _utf8_len(char)
                if used > limit:
                    return text[:index]
            return text
        case LimitUnit.WORDS:
            if limit == 0:
                return ""
            for count, match in enumerate(_WORD.finditer(text), start=1):
                if count == limit:
                    return text[: match.end()]
            return text
        case LimitUnit.TOKENS:
            raise ValueError("token limits have no locally determinable exact prefix")


def prepare_input(
    text: str,
    *,
    max_size: int | None,
    min_size: int | None,
    unit: LimitUnit,
) -> PreparedInput:
    """Apply a provider's documented limits to ``text`` without altering content.

    Raises :class:`ProviderFailure` with ``INPUT_TOO_SHORT`` when the documented hard
    minimum is not met, or ``INPUT_TOO_LARGE`` when the text is too large and no exact
    prefix boundary can be computed.
    """
    size = measure(text, unit)
    if min_size is not None and size is not None and size < min_size:
        raise ProviderFailure(
            ErrorCategory.INPUT_TOO_SHORT,
            f"input has {size} {unit.value}; provider requires at least {min_size}",
        )
    if max_size is None or (size is not None and size <= max_size):
        return PreparedInput(text, len(text), len(text), truncated=False)
    if size is None:
        # Token-based limit: we only know the text is safe if it is trivially small.
        if len(text) <= max_size:
            return PreparedInput(text, len(text), len(text), truncated=False)
        raise ProviderFailure(
            ErrorCategory.INPUT_TOO_LARGE,
            f"input may exceed the provider limit of {max_size} {unit.value}; "
            "no exact prefix boundary can be determined locally",
        )
    prefix = exact_prefix(text, max_size, unit)
    if not prefix:
        raise ProviderFailure(
            ErrorCategory.INPUT_TOO_LARGE, "no non-empty prefix fits the provider limit"
        )
    return PreparedInput(prefix, len(text), len(prefix), truncated=True)
