import json
import time

from playwright.sync_api import expect

from .conftest import STARS


def to_projects(page, site):
    page.goto(site)
    page.locator("#projects").scroll_into_view_if_needed()


def test_live_panel_and_cards(site, page, gh):
    to_projects(page, site)
    panel = page.locator("#gh-panel")
    expect(panel).to_contain_text("Live data from the GitHub API")
    expect(panel).to_contain_text("Public repositories")
    expect(panel.locator(".gh-stat strong").nth(0)).to_have_text("16")
    expect(panel.locator(".gh-stat strong").nth(2)).to_have_text(str(STARS))  # forks of others excluded
    assert panel.locator(".gh-events li").count() == 4
    expect(panel).to_contain_text("Pushed to DSA-Traning")
    expect(page.locator("#pg .pj-live", has_text="Confirmed on GitHub")).to_have_count(6)


def test_cache_then_manual_refresh(site, page, gh):
    to_projects(page, site)
    expect(page.locator("#gh-panel")).to_contain_text("Live data")
    first = gh.api_calls
    assert first == 3
    page.reload(); page.locator("#projects").scroll_into_view_if_needed()
    expect(page.locator("#gh-panel")).to_contain_text("cached")
    assert gh.api_calls == first, "second visit must be served from cache"
    page.get_by_role("button", name="Refresh").click()
    expect(page.locator("#gh-panel")).to_contain_text("fetched")
    assert gh.api_calls == first + 3


def test_no_token_is_ever_sent(site, page, gh):
    to_projects(page, site)
    expect(page.locator("#gh-panel")).to_contain_text("Live data")
    assert gh.auth_headers and set(gh.auth_headers) == {None}


def test_rate_limited_falls_back_with_label(site, page, gh):
    gh.mode = "rate"
    to_projects(page, site)
    panel = page.locator("#gh-panel")
    expect(panel).to_contain_text("Live GitHub data unavailable")
    expect(panel).to_contain_text("rate limit")
    expect(panel).to_contain_text("resets around")
    expect(panel.locator(".gh-stat strong").first).to_have_text("16")
    expect(panel).to_contain_text("not fetched live")
    expect(page.locator("#pg .pj")).to_have_count(6)
    expect(page.locator("#pj-sort option[value=stars]")).to_be_disabled()


def test_stale_cache_survives_rate_limit(site, page, gh):
    to_projects(page, site)
    expect(page.locator("#gh-panel")).to_contain_text("Live data")
    page.evaluate("(()=>{const k='pf.gh.v1',d=JSON.parse(localStorage.getItem(k));d.at-=3600000;localStorage.setItem(k,JSON.stringify(d))})()")
    gh.mode = "rate"
    page.reload(); page.locator("#projects").scroll_into_view_if_needed()
    panel = page.locator("#gh-panel")
    expect(panel).to_contain_text("Showing GitHub data cached")
    expect(panel).to_contain_text("Live refresh failed")
    expect(panel.locator(".gh-stat strong").first).to_have_text("16")


def test_offline_empty_and_server_error(make_page, site, gh):
    for mode, text in [("offline", "could not be reached"), ("500", "returned an error"), ("empty", "no public repositories")]:
        gh.mode = mode
        p = make_page()
        to_projects(p, site)
        expect(p.locator("#gh-panel")).to_contain_text(text)
        expect(p.locator("#pg .pj")).to_have_count(6)  # the portfolio itself never depends on GitHub


def test_filters_search_and_empty_state(site, page):
    to_projects(page, site)
    cards = page.locator("#pg .pj")
    expect(cards).to_have_count(6)
    page.get_by_role("button", name="Web", exact=True).click()
    expect(cards).to_have_count(2)
    expect(page.get_by_role("button", name="Web", exact=True)).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Clear filters").click()
    page.fill("#pj-q", "opencv")
    expect(cards).to_have_count(1)
    expect(page.locator(".pj-count")).to_have_text("Showing 1 of 6 projects")
    page.fill("#pj-q", "zzzz")
    expect(page.locator(".pj-empty")).to_contain_text("No projects match")
    page.locator(".pj-empty").get_by_role("button", name="Clear filters").click()
    expect(cards).to_have_count(6)
    page.select_option("#pj-tech", "Python")
    expect(cards).to_have_count(3)


def test_sorting_with_live_data(site, page):
    to_projects(page, site)
    expect(page.locator("#gh-panel")).to_contain_text("Live data")
    title = lambda: page.locator("#pg .pj h3").first.inner_text()
    assert title() == "Loan Approval Prediction"
    page.select_option("#pj-sort", "name"); assert title() == "Book Recommendation System"
    page.select_option("#pj-sort", "stars"); assert title() == "Smart Traffic Management System"
    page.select_option("#pj-sort", "updated"); assert title() == "DSA Training"


def test_expandable_details_only_show_verified_content(site, page):
    to_projects(page, site)
    btn = page.locator("#pg .more").first
    expect(btn).to_have_attribute("aria-expanded", "false")
    btn.click()
    expect(btn).to_have_attribute("aria-expanded", "true")
    detail = page.locator("#pd-loan-approval")
    expect(detail).to_be_visible()
    expect(detail).to_contain_text("Problem")
    expect(detail).to_contain_text("Implementation")
    expect(detail).not_to_contain_text("Architecture")  # not in the source data, so not invented
    btn.click(); expect(detail).to_be_hidden()
    body = page.inner_text("body")
    assert "Live demo" not in body and "Verified results" not in body


def test_details_work_from_keyboard_and_repo_links_are_the_owners(site, page):
    to_projects(page, site)
    page.locator("#pg .more").nth(3).focus(); page.keyboard.press("Enter")
    expect(page.locator("#pd-fleet-management")).to_contain_text("Docker Compose")
    hrefs = page.locator("#pg a.lk").evaluate_all("els=>els.map(e=>e.href)")
    assert len(hrefs) == 6 and all(h.startswith("https://github.com/poovarasansiva21/") for h in hrefs)
