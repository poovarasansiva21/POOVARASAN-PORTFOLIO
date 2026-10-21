import re
from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]


def test_loads_clean_with_landmarks(site, page):
    page.goto(site)
    expect(page.locator("h1.big")).to_contain_text("Computer Science Engineer")
    assert page.locator("h1").count() == 1, "exactly one h1 (the decorative Contact h1 was removed)"
    expect(page.locator("main#main")).to_have_count(1)
    expect(page.locator("nav[aria-label=Primary]")).to_have_count(1)
    assert page.errors == []


def test_hero_chip_relabelled_and_content_preserved(site, page):
    page.goto(site)
    body = page.inner_text("body")
    for text in ["7.91", "Featured projects", "Things I’ve Built", "Education and Experience", "Competitive Programming", "1490", "Kalaignarkarunanidhi Institute of Technology"]:
        assert text in body, text


def test_skip_link_is_first_tab_stop_and_works(site, page):
    page.goto(site)
    page.keyboard.press("Tab")
    skip = page.locator(".skip")
    expect(skip).to_be_focused()
    expect(skip).to_be_in_viewport()  # slides in over 0.15s
    page.keyboard.press("Enter")
    assert page.url.endswith("#main")


def test_focus_ring_is_visible(site, page):
    page.goto(site)
    page.keyboard.press("Tab"); page.keyboard.press("Tab")
    style = page.evaluate("(()=>{const s=getComputedStyle(document.activeElement);return [s.outlineStyle,parseFloat(s.outlineWidth)]})()")
    assert style[0] == "solid" and style[1] >= 2


def test_works_without_javascript(browser, site):
    ctx = browser.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 900})
    ctx.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=""))
    p = ctx.new_page()
    p.goto(site)
    expect(p.locator("#pre")).to_be_hidden()  # original bug: the preloader covered the page forever
    expect(p.locator("h1.big")).to_have_css("opacity", "1")
    expect(p.locator("#projects .pj")).to_have_count(6)  # static fallback cards
    expect(p.locator("a[href^='mailto:kit28']").first).to_be_visible()
    ctx.close()


def test_preloader_clears_by_itself_with_motion(make_page, site):
    p = make_page(reduced_motion="no-preference")
    p.goto(site)
    expect(p.locator("#pre")).to_have_count(0, timeout=7000)
    assert p.errors == []


def test_reduced_motion_stops_infinite_animations(site, page):
    page.goto(site)
    names = page.evaluate("[...document.querySelectorAll('.chip,.mq div,.star,.sc')].map(e=>getComputedStyle(e).animationName)")
    assert names and set(names) == {"none"}
    assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto"


def test_mobile_menu_is_accessible(make_page, site):
    p = make_page(viewport={"width": 390, "height": 800}, has_touch=True)
    p.goto(site)
    toggle = p.locator("#bg")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(p.locator("#mm a").first).to_be_hidden()  # hidden links must not be reachable by keyboard
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(p.locator("#mm a").first).to_be_visible()
    p.keyboard.press("Escape")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_be_focused()


@pytest.mark.parametrize("width", [320, 375, 768, 1280])
def test_no_horizontal_scroll(make_page, site, width):
    p = make_page(viewport={"width": width, "height": 900})
    p.goto(site)
    p.locator("#projects").scroll_into_view_if_needed()
    assert p.evaluate("document.documentElement.scrollWidth") <= width


def test_custom_404_page(site, page):
    r = page.goto(site + "/definitely/not/here")
    assert r.status == 404
    expect(page.get_by_role("heading", name="This page doesn’t exist")).to_be_visible()
    page.get_by_role("link", name="Back to the portfolio").click()
    expect(page.locator("h1.big")).to_be_visible()


def _axe(page, **kw):
    res = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}, "rules": {"color-contrast": {"enabled": False}}, **kw})
    return [f"{v['id']}: {v['help']} -> {[n['target'] for n in v['nodes']][:3]}" for v in res.response["violations"]]


def test_axe_page_and_open_dialogs(site, page):
    page.goto(site)
    page.locator("#projects").scroll_into_view_if_needed()
    page.locator("#pg .more").first.click()
    assert _axe(page) == []
    page.click("#term-open")
    assert _axe(page) == []
    page.keyboard.press("Escape")
    page.click("#ai-open")
    expect(page.locator(".a-off")).to_be_visible()
    assert _axe(page) == []


def test_no_secrets_or_tokens_in_frontend():
    for f in list((ROOT / "assets").rglob("*.js")) + [ROOT / "index.html"]:
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"ghp_[A-Za-z0-9]{20,}|github_pat_|sk-ant-|Authorization|Bearer ", text), f
    assert not (ROOT / ".env").exists() or "ANTHROPIC_API_KEY=sk" not in (ROOT / ".gitignore").read_text()


def test_dom_is_never_built_from_untrusted_strings():
    """The feature modules must not use innerHTML/outerHTML/insertAdjacentHTML/eval/document.write with data."""
    for f in (ROOT / "assets" / "js").glob("*.js"):
        if f.name in ("main.js", "data.js"):
            continue
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", text), f
        for m in re.finditer(r"innerHTML", text):
            assert f.name == "util.js", f"innerHTML in {f.name}"  # util.js only sets static icon markup
