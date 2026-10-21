import json

from playwright.sync_api import expect


def ask(page, text):
    page.fill("#ai-q", text)
    page.keyboard.press("Enter")


def mock_ready(page, chat):
    page.route("**/api/health", lambda r: r.fulfill(json={"ok": True, "assistant": True, "contact": True}))
    page.route("**/api/chat", chat)


def test_unavailable_state_on_real_backend_without_key(bare, page):
    page.goto(bare)
    page.click("#ai-open")
    off = page.locator(".a-off")
    expect(off).to_contain_text("unavailable right now")
    expect(off).to_contain_text("isn't configured on this server")
    expect(page.locator("#ai-q")).to_have_count(0)
    page.get_by_role("button", name="Open the terminal").click()
    expect(page.locator("dialog#term")).to_be_visible()


def test_unreachable_backend_is_explained(make_page, site):
    p = make_page()
    p.route("**/api/health", lambda r: r.abort())
    p.goto(site); p.click("#ai-open")
    expect(p.locator(".a-off")).to_contain_text("can't be reached")


def test_real_answer_flow_and_labels(site, page):
    seen = {}

    def chat(route):
        seen["body"] = json.loads(route.request.post_data)
        route.fulfill(json={"ok": True, "reply": "He built six projects, e.g. a loan approval model.", "model": "m"})
    mock_ready(page, chat)
    page.goto(site); page.click("#ai-open")
    expect(page.locator("#ai-q")).to_be_visible()
    ask(page, "What has he built?")
    expect(page.locator(".a-assistant").last).to_contain_text("loan approval model")
    expect(page.locator(".a-assistant small").last).to_have_text("AI-generated, may contain mistakes")
    assert seen["body"]["messages"][-1] == {"role": "user", "content": "What has he built?"}
    ask(page, "And skills?")
    expect(page.locator(".a-user")).to_have_count(2)
    assert len(seen["body"]["messages"]) == 3  # history is sent so follow-ups work


def test_reply_is_rendered_as_text_not_html(site, page):
    mock_ready(page, lambda r: r.fulfill(json={"ok": True, "reply": "<img src=x onerror=window.__p=1><b>hi</b>"}))
    page.goto(site); page.click("#ai-open"); ask(page, "x?")
    expect(page.locator(".a-assistant").last).to_contain_text("<b>hi</b>")
    assert page.locator(".a-log img, .a-log b").count() == 0 and page.evaluate("window.__p") is None


def test_rate_limit_error_and_retry(site, page):
    calls = []

    def chat(route):
        calls.append(1)
        if len(calls) == 1:
            route.fulfill(status=429, headers={"retry-after": "42"}, json={"ok": False, "error": "rate_limited"})
        else:
            route.fulfill(json={"ok": True, "reply": "Back again."})
    mock_ready(page, chat)
    page.goto(site); page.click("#ai-open"); ask(page, "hello there")
    expect(page.locator(".a-error")).to_contain_text("Try again in 42 seconds")
    page.get_by_role("button", name="Try again").click()
    expect(page.locator(".a-assistant").last).to_contain_text("Back again.")
    expect(page.locator(".a-error")).to_have_count(0)


def test_server_and_network_errors_never_fake_an_answer(site, page):
    mode = {"m": "500"}
    mock_ready(page, lambda r: r.fulfill(status=502, json={"ok": False, "error": "assistant_error"}) if mode["m"] == "500" else r.abort())
    page.goto(site); page.click("#ai-open"); ask(page, "first question")
    expect(page.locator(".a-error")).to_contain_text("didn't respond properly")
    page.get_by_role("button", name="Try again").click()
    expect(page.locator(".a-error")).to_have_count(1)
    mode["m"] = "abort"
    page.get_by_role("button", name="Try again").click()
    expect(page.locator(".a-error")).to_contain_text("Couldn't reach the assistant")
    assert page.locator(".a-assistant:not(.a-wait)").count() == 1  # only the greeting


def test_input_limit(site, page):
    mock_ready(page, lambda r: r.fulfill(json={"ok": True, "reply": "ok"}))
    page.goto(site); page.click("#ai-open")
    expect(page.locator("#ai-q")).to_have_attribute("maxlength", "500")
