import email
import json
from email import policy

from playwright.sync_api import expect


def respond(status, body, headers=None):
    return lambda route, *_: route.fulfill(status=status, headers=headers or {}, json=body)


def fill(page, **over):
    d = {"fn": "Asha", "ln": "Rao", "em": "asha@example.org", "ms": "Hello Poovarasan, I would like to discuss an internship."}
    d.update(over)
    for k, v in d.items():
        page.fill("#" + k, v)
    page.check("#pe")


def goto(page, url):
    page.goto(url); page.locator("#contact").scroll_into_view_if_needed()
    page.wait_for_timeout(300)


def test_empty_submit_shows_accessible_errors_and_sends_nothing(site, page):
    reqs = []
    page.on("request", lambda r: "/api/contact" in r.url and reqs.append(r))
    goto(page, site)
    page.click(".send")
    expect(page.locator("#err-first_name")).to_have_text("Enter your first name.")
    expect(page.locator("#fn")).to_have_attribute("aria-invalid", "true")
    expect(page.locator("#fn")).to_be_focused()
    expect(page.locator("#form-status")).to_contain_text("Please fix 5 fields")
    assert reqs == []


def test_field_rules(site, page):
    goto(page, site)
    fill(page, em="not-an-email", ms="short")
    page.click(".send")
    expect(page.locator("#err-email")).to_contain_text("valid email")
    expect(page.locator("#err-message")).to_contain_text("at least 10")
    assert page.locator("#fn").get_attribute("aria-invalid") == "false"


def test_real_delivery_end_to_end(site, page, sink):
    before = len(sink.messages)
    goto(page, site)
    fill(page, ms="Hello Poovarasan, this is a real end to end test message.")
    page.wait_for_timeout(400)
    page.click(".send")
    expect(page.locator("#form-status")).to_have_text("Message sent. Thank you, Asha.")
    assert len(sink.messages) == before + 1
    msg = email.message_from_bytes(sink.messages[-1].content, policy=policy.default)
    assert msg["Reply-To"] == "asha@example.org" and "real end to end test" in msg.get_content()
    expect(page.locator("#fn")).to_have_value("")  # form reset only after server confirmation


def test_sending_state_and_no_double_submit(site, page):
    held, hits = [], []
    page.route("**/api/contact", lambda r: (hits.append(1), held.append(r)))
    goto(page, site); fill(page); page.wait_for_timeout(400)
    page.click(".send")
    expect(page.locator(".send")).to_be_disabled()
    expect(page.locator(".send")).to_contain_text("Sending")
    expect(page.locator("#form-status")).to_contain_text("Sending your message")
    assert "Message sent" not in page.inner_text("#form-status")
    held[0].fulfill(json={"ok": True})
    expect(page.locator("#form-status")).to_contain_text("Message sent")
    assert len(hits) == 1


def test_server_failures_never_claim_success(site, page):
    cases = [(502, {"ok": False, "error": "delivery_failed"}, "was not sent", {}),
             (503, {"ok": False, "error": "contact_unavailable"}, "was not sent", {}),
             (429, {"ok": False, "error": "rate_limited"}, "Too many messages", {"retry-after": "300"}),
             (200, {"unexpected": True}, "was not sent", {})]
    for status, body, text, headers in cases:
        page.unroute("**/api/contact")
        page.route("**/api/contact", respond(status, body, headers))
        goto(page, site); fill(page); page.wait_for_timeout(400)
        page.click(".send")
        st = page.locator("#form-status")
        expect(st).to_contain_text(text)
        assert "Message sent" not in st.inner_text()
        expect(st.locator("a.f-mail")).to_have_attribute("href", __import__("re").compile(r"^mailto:kit28\.24cs117@gmail\.com\?subject="))


def test_network_error_never_claims_success(site, page):
    page.route("**/api/contact", lambda r: r.abort())
    goto(page, site); fill(page); page.wait_for_timeout(400)
    page.click(".send")
    expect(page.locator("#form-status")).to_contain_text("Your message was not sent")


def test_server_side_field_errors_are_mapped(site, page):
    page.route("**/api/contact", lambda r: r.fulfill(status=422, json={"ok": False, "error": "validation", "fields": {"message": "Please include at most two links."}}))
    goto(page, site); fill(page); page.wait_for_timeout(400)
    page.click(".send")
    expect(page.locator("#err-message")).to_have_text("Please include at most two links.")


def test_unavailable_backend_offers_mailto_and_says_nothing_was_sent(bare, page):
    goto(page, bare)
    expect(page.locator("#form-status")).to_contain_text("contact service is offline")
    fill(page); page.click(".send")
    st = page.locator("#form-status")
    expect(st).to_contain_text("nothing was sent from this page")
    href = st.locator("a.f-mail").get_attribute("href")
    assert "Hello%20Poovarasan" in href and "Asha%20Rao" in href


def test_honeypot_is_invisible_and_not_tabbable(site, page):
    goto(page, site)
    hp = page.locator("input[name=website]")
    expect(hp).to_have_attribute("tabindex", "-1")
    assert hp.bounding_box()["x"] < -1000
    assert page.locator("label.vh").count() >= 4  # every input has a real label
