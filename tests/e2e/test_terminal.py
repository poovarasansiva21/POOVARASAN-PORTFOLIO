from datetime import datetime

import pytest
from playwright.sync_api import expect


def open_term(page, site):
    page.goto(site)
    page.click("#term-open")
    expect(page.locator("dialog#term")).to_be_visible()
    return page.locator("#term-out")


def run(page, cmd):
    page.fill("#term-cmd", cmd)
    page.keyboard.press("Enter")


def test_launcher_opens_and_focuses_input(site, page):
    out = open_term(page, site)
    expect(page.locator("#term-cmd")).to_be_focused()
    expect(out).to_contain_text("Type \"help\"")


@pytest.mark.parametrize("cmd,expected", [
    ("about", ["Computer Science Engineer", "Coimbatore", "Appin Technology"]),
    ("skills", ["Programming Languages", "Java, Python, C, C++, SQL", "ML & Tools"]),
    ("projects", ["Loan Approval Prediction", "Smart Traffic Management System", "github.com/poovarasansiva21/Fleet-Management-System"]),
    ("contact", ["kit28.24cs117@gmail.com", "+91 87789 31271", "linkedin.com/in/poovarasans21"]),
    ("date", [str(datetime.now().year)]),
])
def test_commands(site, page, cmd, expected):
    out = open_term(page, site)
    run(page, cmd)
    for e in expected:
        expect(out).to_contain_text(e)


def test_help_lists_every_supported_command(site, page):
    out = open_term(page, site)
    run(page, "help")
    for c in ["help", "about", "skills", "projects", "github", "contact", "clear", "date"]:
        expect(out).to_contain_text(c)


def test_clear(site, page):
    out = open_term(page, site)
    run(page, "about"); expect(out).to_contain_text("Appin")
    run(page, "clear")
    expect(out.locator(".t-line")).to_have_count(0)


def test_github_command_live_and_labelled(site, page, gh):
    out = open_term(page, site)
    run(page, "github")
    expect(out).to_contain_text("16 public repos, 4 followers, 18 stars, 6 forks")
    expect(out).to_contain_text("Live data from the GitHub API")
    expect(out).to_contain_text("Pushed to DSA-Traning")


def test_github_command_fallback_when_rate_limited(site, page, gh):
    gh.mode = "rate"
    out = open_term(page, site)
    run(page, "github")
    expect(out).to_contain_text("Live GitHub data unavailable")
    expect(out).to_contain_text("rate limit")
    expect(out).to_contain_text("not fetched live")


@pytest.mark.parametrize("evil", [
    "alert('xss')", "<img src=x onerror=window.__pwned=1>", "rm -rf /", "constructor", "__proto__", "toString",
    "help; date", "$(date)", "`date`", "window.__pwned=1", "javascript:alert(1)",
])
def test_unsupported_input_is_never_executed(site, page, evil):
    out = open_term(page, site)
    run(page, evil)
    expect(out).to_contain_text("command not found")
    assert page.evaluate("window.__pwned") is None
    assert out.locator("img, script, iframe").count() == 0
    assert page.dialogs == [] and page.errors == []


def test_arguments_are_rejected_not_interpreted(site, page):
    out = open_term(page, site)
    run(page, "date --help")
    expect(out).to_contain_text("takes no arguments")


def test_history_navigation_and_tab_completion(site, page):
    open_term(page, site)
    inp = page.locator("#term-cmd")
    run(page, "help"); run(page, "about")
    page.keyboard.press("ArrowUp"); expect(inp).to_have_value("about")
    page.keyboard.press("ArrowUp"); expect(inp).to_have_value("help")
    page.keyboard.press("ArrowDown"); expect(inp).to_have_value("about")
    page.keyboard.press("ArrowDown"); expect(inp).to_have_value("")
    page.fill("#term-cmd", "sk"); page.keyboard.press("Tab")
    expect(inp).to_have_value("skills")


def test_escape_closes_and_returns_focus(site, page):
    open_term(page, site)
    page.keyboard.press("Escape")
    expect(page.locator("dialog#term")).to_be_hidden()
    expect(page.locator("#term-open")).to_be_focused()


def test_keyboard_only_open(site, page):
    page.goto(site)
    page.locator("#term-open").focus()
    page.keyboard.press("Enter")
    expect(page.locator("dialog#term")).to_be_visible()


def test_focus_is_trapped_inside_dialog(site, page):
    open_term(page, site)
    for _ in range(12):
        page.keyboard.press("Tab")
        assert page.evaluate("!!document.activeElement.closest('dialog#term') || document.activeElement===document.body || document.activeElement.tagName==='HTML'")


def test_mobile_quick_command_buttons(make_page, site):
    p = make_page(viewport={"width": 390, "height": 760}, has_touch=True, is_mobile=True)
    p.goto(site)
    p.tap("#term-open")
    box = p.locator("dialog#term").bounding_box()
    assert box["width"] >= 389 and box["height"] >= 700, "full-screen on phones"
    p.locator(".t-chips button", has_text="skills").tap()
    expect(p.locator("#term-out")).to_contain_text("Programming Languages")
    assert p.evaluate("parseFloat(getComputedStyle(document.querySelector('#term-cmd')).fontSize)") >= 16, "16px+ avoids iOS zoom"
    assert p.locator(".t-chips button").first.bounding_box()["height"] >= 40


def test_dialogs_are_centered_on_desktop(site, page):
    open_term(page, site)
    b = page.locator("dialog#term").bounding_box()
    vw, vh = 1280, 900
    assert abs((b["x"] + b["width"] / 2) - vw / 2) < 2 and abs((b["y"] + b["height"] / 2) - vh / 2) < 2
    page.keyboard.press("Escape"); page.click("#ai-open")
    a = page.locator("dialog#ai").bounding_box()
    assert abs((a["x"] + a["width"] / 2) - vw / 2) < 2
