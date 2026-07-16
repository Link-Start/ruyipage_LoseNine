# -*- coding: utf-8 -*-
"""Regression tests for viewport timeout fallback in set_window_size()."""

from types import SimpleNamespace

from ruyipage._pages.firefox_base import FirefoxBase
from ruyipage.errors import BiDiError


class _FakeWindow:
    def __init__(self):
        self.sizes = []

    def set_size(self, width, height):
        self.sizes.append((width, height))


class _FakeBrowserDriver:
    def __init__(self):
        self.calls = []

    def run(self, method, params=None, timeout=None):
        self.calls.append((method, params or {}, timeout))
        if method == "browsingContext.setViewport":
            raise BiDiError("timeout", "command timeout")
        if method == "script.addPreloadScript":
            return {"script": "viewport-fallback"}
        return {}


def _make_page():
    page = FirefoxBase.__new__(FirefoxBase)
    FirefoxBase.__init__(page)
    browser_driver = _FakeBrowserDriver()
    page._driver = SimpleNamespace(_browser_driver=browser_driver)
    page._context_id = "context-1"
    page._window = _FakeWindow()
    return page, browser_driver


def test_set_window_size_falls_back_when_set_viewport_times_out():
    page, browser_driver = _make_page()

    page.set_window_size(1360, 700)

    assert page._window.sizes == [(1360, 700)]

    calls = browser_driver.calls
    methods = [method for method, _params, _timeout in calls]
    assert "browsingContext.setViewport" in methods
    assert "script.addPreloadScript" in methods
    assert "script.callFunction" in methods

    viewport_call = next(
        call for call in calls if call[0] == "browsingContext.setViewport"
    )
    assert viewport_call[2] == 3

    preload_call = next(call for call in calls if call[0] == "script.addPreloadScript")
    call_function = next(call for call in calls if call[0] == "script.callFunction")
    assert preload_call[2] == 3
    assert call_function[2] == 3
    assert preload_call[1]["contexts"] == ["context-1"]
    script = preload_call[1]["functionDeclaration"]
    assert "innerWidth" in script
    assert "innerHeight" in script
    assert "visualViewport" in script
    assert "1360" in script
    assert "700" in script
