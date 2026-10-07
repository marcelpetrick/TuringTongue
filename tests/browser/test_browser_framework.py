# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Browser fallback framework, exercised with a fake page (no real browser needed)."""

import builtins
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from turingtongue import Checker, Registry, Settings
from turingtongue.browser import playwright_support
from turingtongue.browser.base import BrowserProvider
from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory, TransportKind
from turingtongue.normalization.labels import label_to_evidence
from turingtongue.providers.base import Detection, DetectionOptions

pytestmark = pytest.mark.unit


class FakePage:
    def __init__(self) -> None:
        self.filled = ""
        self.visited = ""

    async def goto(self, url: str, timeout: float) -> None:
        self.visited = url

    async def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"png")

    async def content(self) -> str:
        return "<html>result</html>"


@contextlib.asynccontextmanager
async def fake_page() -> AsyncIterator[FakePage]:
    yield FakePage()


class DemoSite(BrowserProvider):
    url = "https://detector.example.test/"
    page_factory = staticmethod(fake_page)

    async def submit(self, page: Any, text: str, options: DetectionOptions) -> None:
        if text == "explode":
            raise RuntimeError("selector not found")
        page.filled = text

    async def wait_for_result(self, page: Any, options: DetectionOptions) -> None:
        assert page.filled

    async def parse(self, page: Any) -> Detection:
        return Detection(
            evidence=label_to_evidence("ai") or 0.0, score_semantics="label", raw_label="ai"
        )


def _registry(terms: str) -> Registry:
    return Registry.from_toml(
        f"""
[providers.demo]
name = "Demo site"
transport = "browser"
adapter = "tests.browser.test_browser_framework:DemoSite"
requires_credentials = false
automation_terms = "{terms}"
terms_reviewed = "2026-10-07"
"""
    )


def _check(terms: str, text: str = "Some text.", **options: object):  # type: ignore[no-untyped-def]
    checker = Checker(Settings(env={}), registry=_registry(terms))
    return checker.check(
        text, transport="browser", providers=["demo"], provider_options={"demo": options}
    )


def test_terms_gate_refuses() -> None:
    error = _check("forbidden").errors[0]
    assert error.category is ErrorCategory.TERMS_NOT_PERMITTED
    assert "2026-10-07" in error.message


def test_permitted_site_runs_with_phase_timings(tmp_path: Path) -> None:
    result = _check("permitted", debug_dir=str(tmp_path))
    p = result.providers[0]
    assert p.ok
    assert p.transport is TransportKind.BROWSER
    assert {w.split("=")[0] for w in p.warning_codes} == {
        "PHASE_STARTUP_MS",
        "PHASE_NAVIGATE_MS",
        "PHASE_SUBMIT_MS",
        "PHASE_WAIT_RESULT_MS",
        "PHASE_PARSE_MS",
    }
    assert (tmp_path / "demo.png").exists()
    assert (tmp_path / "demo.html").read_text() == "<html>result</html>"


def test_phase_failure_is_categorized() -> None:
    error = _check("permitted", text="explode").errors[0]
    assert error.category is ErrorCategory.BROWSER_AUTOMATION_FAILED
    assert "'submit'" in error.message


def test_api_transport_excludes_browser() -> None:
    checker = Checker(Settings(env={}), registry=_registry("permitted"))
    assert checker.select(["demo"], "api").run == []


async def test_missing_playwright_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("playwright"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(ProviderFailure, match="optional extra") as info:
        async with playwright_support.fresh_page():
            pass  # pragma: no cover
    assert info.value.category is ErrorCategory.BROWSER_AUTOMATION_FAILED


def test_api_package_imports_without_browser_modules() -> None:
    import subprocess
    import sys

    code = "import sys, turingtongue; turingtongue.Checker; print('playwright' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


@pytest.mark.browser
async def test_real_chromium_blank_page() -> None:  # pragma: no cover - opt-in, needs browsers
    async with playwright_support.fresh_page() as page:
        await page.goto("about:blank")
        assert await page.title() == ""


class _FakeContext:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    async def new_page(self) -> str:
        self.log.append("page")
        return "PAGE"

    async def close(self) -> None:
        self.log.append("context-closed")


class _FakeBrowser(_FakeContext):
    async def new_context(self) -> _FakeContext:
        self.log.append("context")
        return _FakeContext(self.log)

    async def close(self) -> None:
        self.log.append("browser-closed")


async def test_fresh_page_isolates_and_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []

    class Chromium:
        async def launch(self, headless: bool) -> _FakeBrowser:
            log.append(f"launch headless={headless}")
            return _FakeBrowser(log)

    class Playwright:
        chromium = Chromium()

    @contextlib.asynccontextmanager
    async def fake_async_playwright() -> AsyncIterator[Playwright]:
        yield Playwright()

    monkeypatch.setattr(playwright_support, "_import_playwright", lambda: fake_async_playwright)
    async with BrowserProvider.page_factory() as page:
        assert page == "PAGE"
    assert log == ["launch headless=True", "context", "page", "context-closed", "browser-closed"]
