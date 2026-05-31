# -*- coding: utf-8 -*-

from unittest import mock

from ruyipage import FirefoxOptions, FirefoxPage


def test_page_new_tab_forwards_user_context():
    page = FirefoxPage.__new__(FirefoxPage)
    fake_browser = mock.Mock()
    page._firefox = fake_browser

    page.new_tab("https://example.com", background=True, user_context="ctx-1")

    fake_browser.new_tab.assert_called_once_with(
        "https://example.com", True, user_context="ctx-1"
    )


def test_page_new_container_tab_forwards_to_browser():
    page = FirefoxPage.__new__(FirefoxPage)
    fake_browser = mock.Mock()
    page._firefox = fake_browser

    page.new_container_tab("https://example.com", background=True)

    fake_browser.new_container_tab.assert_called_once_with(
        url="https://example.com", background=True
    )


def test_page_new_container_tabs_forwards_to_browser():
    page = FirefoxPage.__new__(FirefoxPage)
    fake_browser = mock.Mock()
    page._firefox = fake_browser

    page.new_container_tabs(5, "https://example.com", background=False)

    fake_browser.new_container_tabs.assert_called_once_with(
        count=5, url="https://example.com", background=False
    )


def test_browser_new_tab_includes_user_context():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser._context_ids = ["root-ctx"]
    browser._contexts = {}
    browser._driver = mock.Mock()
    browser._driver.run.return_value = {"context": "ctx-2"}
    browser._get_or_create_tab = mock.Mock(return_value=mock.Mock())

    browser.new_tab(user_context="uc-1")

    browser._driver.run.assert_called_once_with(
        "browsingContext.create",
        {
            "type": "tab",
            "background": False,
            "referenceContext": "root-ctx",
            "userContext": "uc-1",
        },
    )


def test_browser_new_container_tab_creates_user_context_then_tab():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser._driver = mock.Mock()
    browser.new_tab = mock.Mock(return_value="tab-1")
    browser._driver.run.return_value = {"userContext": "uc-2"}

    result = browser.new_container_tab(url="https://example.com", background=True)

    assert result == "tab-1"
    browser._driver.run.assert_called_once_with("browser.createUserContext")
    browser.new_tab.assert_called_once_with(
        url="https://example.com", background=True, user_context="uc-2"
    )


def test_browser_new_container_tabs_with_count_one_uses_bidi_path():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser.new_container_tab = mock.Mock(return_value="tab-1")

    tabs = browser.new_container_tabs(1, url="https://example.com", background=False)

    assert tabs == ["tab-1"]
    browser.new_container_tab.assert_called_once_with(
        url="https://example.com", background=False
    )


def test_page_tab_properties_forward_to_browser():
    page = FirefoxPage.__new__(FirefoxPage)
    fake_browser = mock.Mock()
    fake_browser.tabs_count = 3
    fake_browser.tab_ids = ["ctx-1", "ctx-2", "ctx-3"]
    fake_browser.latest_tab = "tab-3"
    page._firefox = fake_browser

    assert page.tabs_count == 3
    assert page.tab_ids == ["ctx-1", "ctx-2", "ctx-3"]
    assert page.latest_tab == "tab-3"


def test_page_get_tab_and_get_tabs_forward_to_browser():
    page = FirefoxPage.__new__(FirefoxPage)
    fake_browser = mock.Mock()
    fake_browser.get_tab.return_value = "tab-1"
    fake_browser.get_tabs.return_value = ["tab-1", "tab-2"]
    page._firefox = fake_browser

    assert page.get_tab("ctx-1", title="Example", url="example.com") == "tab-1"
    assert page.get_tabs(title="Example", url="example.com") == ["tab-1", "tab-2"]

    fake_browser.get_tab.assert_called_once_with(
        "ctx-1", "Example", "example.com"
    )
    fake_browser.get_tabs.assert_called_once_with("Example", "example.com")


def test_page_close_other_tabs_defaults_to_current_context():
    page = FirefoxPage.__new__(FirefoxPage)
    fake_browser = mock.Mock()
    page._firefox = fake_browser
    page._context_id = "ctx-current"

    page.close_other_tabs()

    fake_browser.close_tabs.assert_called_once_with("ctx-current", others=True)


def test_page_quit_calls_browser_and_removes_page_cache():
    page = FirefoxPage.__new__(FirefoxPage)
    fake_browser = mock.Mock()
    fake_browser.address = "127.0.0.1:9999"
    page._firefox = fake_browser
    FirefoxPage._PAGES[fake_browser.address] = page

    try:
        page.quit(timeout=7, force=True)
    finally:
        FirefoxPage._PAGES.pop(fake_browser.address, None)

    fake_browser.quit.assert_called_once_with(7, True)
    assert fake_browser.address not in FirefoxPage._PAGES


def test_browser_tab_ids_returns_copy_after_refresh():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser._context_ids = ["ctx-1", "ctx-2"]
    browser._refresh_tabs = mock.Mock()

    tab_ids = browser.tab_ids
    tab_ids.append("ctx-3")

    browser._refresh_tabs.assert_called_once_with()
    assert tab_ids == ["ctx-1", "ctx-2", "ctx-3"]
    assert browser._context_ids == ["ctx-1", "ctx-2"]


def test_browser_latest_tab_returns_last_context_or_none():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser._context_ids = []
    browser._refresh_tabs = mock.Mock()
    browser._get_or_create_tab = mock.Mock()

    assert browser.latest_tab is None

    browser._context_ids = ["ctx-1", "ctx-2"]
    browser._get_or_create_tab.return_value = "tab-2"

    assert browser.latest_tab == "tab-2"
    browser._get_or_create_tab.assert_called_once_with("ctx-2")


def test_browser_get_tab_supports_default_index_negative_and_string_lookup():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser._context_ids = ["ctx-1", "ctx-2"]
    browser._refresh_tabs = mock.Mock()
    browser._get_or_create_tab = mock.Mock(side_effect=lambda ctx_id: "tab-" + ctx_id)

    assert browser.get_tab() == "tab-ctx-1"
    assert browser.get_tab(1) == "tab-ctx-1"
    assert browser.get_tab(-1) == "tab-ctx-2"
    assert browser.get_tab("ctx-2") == "tab-ctx-2"
    assert browser.get_tab("missing") is None


def test_browser_get_tab_returns_none_for_out_of_range_negative_index():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser._context_ids = ["ctx-1"]
    browser._refresh_tabs = mock.Mock()
    browser._get_or_create_tab = mock.Mock()

    assert browser.get_tab(-999) is None
    browser._get_or_create_tab.assert_not_called()


def test_browser_get_tabs_filters_by_title_and_url():
    from ruyipage._base.browser import Firefox

    matching_tab = mock.Mock(title="Example Home", url="https://example.com/home")
    other_tab = mock.Mock(title="Other", url="https://other.test/")
    tabs_by_context = {"ctx-1": matching_tab, "ctx-2": other_tab}
    browser = Firefox.__new__(Firefox)
    browser._context_ids = ["ctx-1", "ctx-2"]
    browser._refresh_tabs = mock.Mock()
    browser._get_or_create_tab = mock.Mock(side_effect=tabs_by_context.get)

    assert browser.get_tabs(title="Example", url="example.com") == [matching_tab]


def test_browser_new_tab_omits_user_context_for_default_context():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)
    browser._context_ids = ["ctx-root"]
    browser._driver = mock.Mock()
    browser._driver.run.return_value = {"context": "ctx-new"}
    browser._get_or_create_tab = mock.Mock(return_value=mock.Mock())

    browser.new_tab(background=True)

    browser._driver.run.assert_called_once_with(
        "browsingContext.create",
        {"type": "tab", "background": True, "referenceContext": "ctx-root"},
    )


def test_browser_new_container_tabs_rejects_non_positive_count():
    from ruyipage._base.browser import Firefox

    browser = Firefox.__new__(Firefox)

    try:
        browser.new_container_tabs(0)
    except ValueError as e:
        assert "count" in str(e)
    else:
        raise AssertionError("expected ValueError for non-positive count")


def test_set_per_tab_proxies_normalizes_lines_and_generates_runtime_fpfile(tmp_path):
    opts = FirefoxOptions()
    opts.set_user_dir(str(tmp_path))
    opts.set_per_tab_proxies(
        [
            "proxy.example.com:1000:user-a:pass-a",
            "socks5://proxy2.example.com:1001:user-b:pass-b",
        ],
        exhausted="wrap",
    )

    opts.prepare_runtime_files()

    assert opts.fpfile.endswith("ruyipage_per_tab_proxy_fp.txt")
    content = (tmp_path / "ruyipage_per_tab_proxy_fp.txt").read_text(encoding="utf-8")
    assert "proxy.rotate.enabled=true" in content
    assert "proxy.rotate.exhausted=wrap" in content
    assert "proxy.rotate.proxy=socks5://proxy.example.com:1000:user-a:pass-a" in content
    assert "proxy.rotate.proxy=socks5://proxy2.example.com:1001:user-b:pass-b" in content


def test_prepare_runtime_files_merges_source_fpfile_and_omits_old_rotate_lines(tmp_path):
    source = tmp_path / "source_fp.txt"
    source.write_text(
        "\n".join(
            [
                "webdriver:0",
                "proxy.rotate.enabled=false",
                "proxy.rotate.exhausted=stop",
                "proxy.rotate.proxy=socks5://old.example.com:9000:old:secret",
                "canvas:123",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    opts = FirefoxOptions()
    opts.set_user_dir(str(tmp_path))
    opts.set_fpfile(str(source))
    opts.set_per_tab_proxies(["proxy.example.com:1000:user-a:pass-a"])

    opts.prepare_runtime_files()

    content = (tmp_path / "ruyipage_per_tab_proxy_fp.txt").read_text(encoding="utf-8")
    assert "webdriver:0" in content
    assert "canvas:123" in content
    assert "proxy.rotate.enabled=false" not in content
    assert "old.example.com" not in content
    assert "proxy.rotate.enabled=true" in content
    assert "proxy.rotate.proxy=socks5://proxy.example.com:1000:user-a:pass-a" in content


def test_write_prefs_does_not_write_global_proxy_for_per_tab_rotate(tmp_path):
    opts = FirefoxOptions()
    opts.set_user_dir(str(tmp_path))
    opts.set_per_tab_proxies(["proxy.example.com:1000:user-a:pass-a"])
    opts.prepare_runtime_files()

    opts.write_prefs_to_profile()

    content = (tmp_path / "user.js").read_text(encoding="utf-8")
    assert "network.proxy.socks" not in content
    assert "network.proxy.socks_port" not in content
    assert "user-a" not in content
    assert "pass-a" not in content


def test_set_per_tab_proxies_validates_format():
    opts = FirefoxOptions()

    try:
        opts.set_per_tab_proxies(["bad-format"])
    except ValueError as e:
        assert "host:port:username:password" in str(e)
    else:
        raise AssertionError("expected ValueError for invalid proxy format")
