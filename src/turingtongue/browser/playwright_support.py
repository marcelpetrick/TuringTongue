# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Lazy Playwright access with a fresh, non-persistent browser context per run."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory


def _import_playwright() -> Any:
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415
    except ImportError as exc:
        raise ProviderFailure(
            ErrorCategory.BROWSER_AUTOMATION_FAILED,
            "browser providers need the optional extra: pip install 'turingtongue[browser]' "
            "and 'playwright install chromium'",
            retryable=False,
        ) from exc
    return async_playwright


@contextlib.asynccontextmanager
async def fresh_page(*, headless: bool = True) -> AsyncIterator[Any]:
    """Yield a page in a brand-new, isolated context; nothing is persisted afterwards.

    The context is ordinary session isolation — not a tool to reset provider quotas.
    """
    async_playwright = _import_playwright()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        try:
            context = await browser.new_context()
            try:
                yield await context.new_page()
            finally:
                await context.close()
        finally:
            await browser.close()
