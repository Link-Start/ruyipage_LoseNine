# -*- coding: utf-8 -*-

from types import SimpleNamespace
from urllib.parse import quote

import pytest

from ruyipage._bidi import script as bidi_script
from ruyipage._pages.firefox_base import FirefoxBase, _frame_url_matches


class TreeDriver:
    def __init__(self, tree, script_result=None, script_error=None):
        self.tree = tree
        self.calls = []
        self.script_result = script_result or {
            "type": "success",
            "result": {"type": "undefined"},
        }
        self.script_error = script_error

    def run(self, method, params=None, timeout=None):
        self.calls.append((method, params, timeout))
        if method == "browsingContext.getTree":
            assert params == {"root": "page-ctx"}
            return self.tree
        if method == "script.callFunction":
            if self.script_error is not None:
                raise self.script_error
            return self.script_result
        raise AssertionError(f"unexpected method: {method}")


class FrameElement:
    def __init__(self, src, shared_id="frame-node"):
        self.src = src
        self.shared_id = shared_id

    def attr(self, name):
        assert name == "src"
        return self.src

    def _make_shared_ref(self):
        return {"type": "sharedReference", "sharedId": self.shared_id}


def make_page(tree, script_result=None, script_error=None):
    browser_driver = TreeDriver(
        tree,
        script_result=script_result,
        script_error=script_error,
    )
    page = object.__new__(FirefoxBase)
    page._context_id = "page-ctx"
    page._driver = SimpleNamespace(_browser_driver=browser_driver)
    page._browser = SimpleNamespace(
        driver=browser_driver,
        options=SimpleNamespace(load_mode="normal"),
    )
    return page


def test_get_all_frames_returns_nested_frames_depth_first():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {
                            "context": "frame-a",
                            "children": [
                                {"context": "frame-a-1"},
                                {"context": "frame-a-2", "children": []},
                            ],
                        },
                        {"context": "frame-b", "children": []},
                    ],
                }
            ]
        }
    )

    frames = page.get_all_frames()

    assert [frame._context_id for frame in frames] == [
        "frame-a",
        "frame-a-1",
        "frame-a-2",
        "frame-b",
    ]
    assert frames[0]._parent is page
    assert frames[1]._parent is frames[0]
    assert frames[2]._parent is frames[0]
    assert frames[3]._parent is page


def test_get_frame_locator_matches_default_https_port_url():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {
                            "context": "frame-a",
                            "url": "https://other.test/path?q=1",
                        },
                        {
                            "context": "frame-b",
                            "url": "https://example.test:443/path?q=1",
                        },
                    ],
                }
            ]
        }
    )
    page.ele = lambda locator: FrameElement("https://example.test/path?q=1")

    frame = page.get_frame("#target-frame")

    assert frame is not None
    assert frame._context_id == "frame-b"
    assert frame._parent is page


def test_frame_url_match_only_strips_default_ports():
    assert _frame_url_matches(
        "https://example.test/path?q=1",
        "https://example.test:443/path?q=1",
    )
    assert _frame_url_matches(
        "http://example.test/path",
        "http://example.test:80/path",
    )
    assert not _frame_url_matches(
        "https://example.test/path",
        "https://example.test:444/path",
    )


def test_get_frame_locator_uses_window_proxy_context_for_second_srcdoc():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {"context": "frame-a", "url": "about:srcdoc"},
                        {"context": "frame-b", "url": "about:srcdoc"},
                    ],
                }
            ]
        },
        script_result={
            "type": "success",
            "result": {
                "type": "window",
                "value": {"context": "frame-b"},
            },
        },
    )
    page.ele = lambda locator: FrameElement("", shared_id="second-node")

    frame = page.get_frame("#second")

    assert frame._context_id == "frame-b"
    call = next(
        call
        for call in page._driver._browser_driver.calls
        if call[0] == "script.callFunction"
    )
    assert call[1]["functionDeclaration"] == "(frame) => frame.contentWindow"
    assert call[1]["target"] == {"context": "page-ctx"}
    assert call[1]["arguments"] == [
        {"type": "sharedReference", "sharedId": "second-node"}
    ]
    assert call[1]["resultOwnership"] == "none"


def test_get_frame_locator_returns_none_when_direct_and_url_matching_fail():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {"context": "frame-a", "url": "https://one.test/frame"},
                        {"context": "frame-b", "url": "https://two.test/frame"},
                    ],
                }
            ]
        }
    )
    page.ele = lambda locator: FrameElement("not-a-frame-url")

    assert page.get_frame("#missing") is None


@pytest.mark.browser
def test_get_frame_locator_maps_second_srcdoc_in_real_firefox(page):
    html = """<!doctype html>
    <html><body>
      <iframe id="first" srcdoc="<p id='value'>A</p>"></iframe>
      <iframe id="second" srcdoc="<p id='value'>B</p>"></iframe>
    </body></html>"""
    page.get("data:text/html;charset=utf-8," + quote(html))

    second = page.ele("#second")
    direct = bidi_script.call_function(
        page._driver._browser_driver,
        page._context_id,
        "(frame) => frame.contentWindow",
        arguments=[second._make_shared_ref()],
        result_ownership="none",
    )
    remote_value = direct["result"]
    expected_context = remote_value["value"]["context"]

    assert direct["type"] == "success"
    assert remote_value["type"] == "window"
    assert "handle" not in remote_value

    frame = page.get_frame("#second")

    assert (frame._context_id, frame.ele("#value").text) == (
        expected_context,
        "B",
    )


def test_get_frame_locator_falls_back_to_default_port_url_when_direct_raises():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {
                            "context": "frame-a",
                            "url": "https://other.test/path?q=1",
                        },
                        {
                            "context": "frame-b",
                            "url": "https://example.test:443/path?q=1",
                        },
                    ],
                }
            ]
        },
        script_error=RuntimeError("contentWindow unavailable"),
    )
    page.ele = lambda locator: FrameElement("https://example.test/path?q=1")

    frame = page.get_frame("#target-frame")

    assert frame._context_id == "frame-b"
    assert any(
        method == "script.callFunction"
        for method, _, _ in page._driver._browser_driver.calls
    )


def test_get_frame_locator_keeps_single_child_fallback():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {"context": "frame-only", "url": "about:blank"},
                    ],
                }
            ]
        }
    )
    page.ele = lambda locator: FrameElement("not-a-frame-url")

    frame = page.get_frame("#only")

    assert frame._context_id == "frame-only"


def test_get_frame_context_id_returns_before_tree_lookup():
    page = make_page({"contexts": []})

    frame = page.get_frame(context_id="frame-direct")

    assert frame._context_id == "frame-direct"
    assert page._driver._browser_driver.calls == []


def test_get_frame_index_takes_priority_over_locator_without_script_call():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {"context": "frame-a"},
                        {"context": "frame-b"},
                    ],
                }
            ]
        }
    )
    page.ele = lambda locator: pytest.fail("locator must not be evaluated")

    frame = page.get_frame(locator="#second", index=1)

    assert frame._context_id == "frame-b"
    assert all(
        method != "script.callFunction"
        for method, _, _ in page._driver._browser_driver.calls
    )


def test_get_frame_without_selector_returns_first_child():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {"context": "frame-a"},
                        {"context": "frame-b"},
                    ],
                }
            ]
        }
    )

    frame = page.get_frame()

    assert frame._context_id == "frame-a"


def test_get_frame_locator_accepts_direct_context_created_after_tree_snapshot():
    page = make_page(
        {
            "contexts": [
                {
                    "context": "page-ctx",
                    "children": [
                        {"context": "frame-old", "url": "about:blank"},
                    ],
                }
            ]
        },
        script_result={
            "type": "success",
            "result": {
                "type": "window",
                "value": {"context": "frame-new"},
            },
        },
    )
    page.ele = lambda locator: FrameElement("", shared_id="new-node")

    frame = page.get_frame("#new")

    assert frame._context_id == "frame-new"
