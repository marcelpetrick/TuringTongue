# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Base class for site-specific browser adapters (vision §13).

There is deliberately no generic "scrape any detector" mechanism. A concrete adapter
declares its URL, selectors, waits and result parser, and the registry entry must
record ``automation_terms = "permitted"`` plus the date the site's terms were
reviewed. Without that the adapter refuses to run (``TERMS_NOT_PERMITTED``).

Phase timings (startup, navigate, submit, wait_result, parse) are reported. Screenshot
/ HTML capture happens only when the ``debug_dir`` provider option is set; captured
pages may contain the submitted text, so this is opt-in debug behaviour.
"""

from __future__ import annotations

import abc
import contextlib
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import httpx

from turingtongue.config import Settings
from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory
from turingtongue.normalization.limits import PreparedInput
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.registry import ProviderSpec
from turingtongue.transport import HttpCaller

PageFactory = Callable[[], contextlib.AbstractAsyncContextManager[Any]]


def _default_page_factory() -> contextlib.AbstractAsyncContextManager[Any]:
    from turingtongue.browser.playwright_support import fresh_page  # noqa: PLC0415

    return fresh_page()


class BrowserProvider(BaseProvider):
    """Site-specific browser adapter skeleton with terms gate and phase timing."""

    url: str = ""
    page_factory: PageFactory = staticmethod(_default_page_factory)

    def __init__(self, spec: ProviderSpec, settings: Settings, client: httpx.AsyncClient) -> None:
        super().__init__(spec, settings, client)
        self.phases: dict[str, float] = {}

    @abc.abstractmethod
    async def submit(self, page: Any, text: str, options: DetectionOptions) -> None:
        """Fill the site's form with ``text`` exactly and start the analysis."""

    @abc.abstractmethod
    async def wait_for_result(self, page: Any, options: DetectionOptions) -> None:
        """Wait on an explicit, site-specific condition (never a blind sleep)."""

    @abc.abstractmethod
    async def parse(self, page: Any) -> Detection:
        """Read the result from the page."""

    @contextlib.asynccontextmanager
    async def _phase(self, name: str) -> AsyncIterator[None]:
        started = time.perf_counter()
        try:
            yield
        except ProviderFailure:
            raise
        except Exception as exc:
            raise ProviderFailure(
                ErrorCategory.BROWSER_AUTOMATION_FAILED,
                f"{self.spec.name}: browser phase '{name}' failed ({type(exc).__name__})",
                retryable=False,
            ) from exc
        finally:
            self.phases[name] = (time.perf_counter() - started) * 1000

    def _check_terms(self) -> None:
        if self.spec.extra.get("automation_terms") != "permitted":
            raise ProviderFailure(
                ErrorCategory.TERMS_NOT_PERMITTED,
                f"{self.spec.name}: the site's terms do not permit automated use "
                f"(reviewed {self.spec.extra.get('terms_reviewed', 'never')})",
                retryable=False,
            )

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        self._check_terms()
        async with self._phase("startup"):
            page_cm = type(self).page_factory()
            page = await page_cm.__aenter__()
        try:
            async with self._phase("navigate"):
                await page.goto(self.url, timeout=options.timeout_s * 1000)
            async with self._phase("submit"):
                await self.submit(page, prepared.text, options)
            async with self._phase("wait_result"):
                await self.wait_for_result(page, options)
            async with self._phase("parse"):
                detection = await self.parse(page)
            await self._debug_capture(page, options)
        finally:
            await page_cm.__aexit__(None, None, None)
        detection.warnings.extend(f"PHASE_{k.upper()}_MS={v:.0f}" for k, v in self.phases.items())
        return detection

    async def _debug_capture(self, page: Any, options: DetectionOptions) -> None:
        directory = options.provider_options.get("debug_dir")
        if not directory:
            return
        target = Path(str(directory))
        target.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(target / f"{self.spec.id}.png"))
        (target / f"{self.spec.id}.html").write_text(await page.content(), encoding="utf-8")
