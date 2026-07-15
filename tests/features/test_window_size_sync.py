# -*- coding: utf-8 -*-
"""Regression tests for runtime window size synchronization."""

import pytest


@pytest.mark.feature
def test_page_set_window_size_syncs_window_viewport_and_screen(page):
    page.get("about:blank")

    page.set_window_size(960, 640)
    page.wait(0.3)

    metrics = page.run_js(
        """
        return {
          outer: {w: window.outerWidth, h: window.outerHeight},
          inner: {w: window.innerWidth, h: window.innerHeight},
          screen: {w: screen.width, h: screen.height}
        };
        """,
        as_expr=False,
    )

    assert metrics["outer"] == {"w": 960, "h": 640}
    assert metrics["inner"] == {"w": 960, "h": 640}
    assert metrics["screen"] == {"w": 960, "h": 640}
    assert page.rect.window_size == (960, 640)
    assert page.rect.viewport_size == (960, 640)
