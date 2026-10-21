import dataclasses
import email
from email import policy

from .conftest import GOOD


def post(c, **over):
    return c.post("/api/contact", json={**GOOD, **over})


def test_unconfigured_reports_unavailable(make_client):
    c = make_client()
    assert c.get("/api/health").json()["contact"] is False
    r = post(c)
    assert r.status_code == 503 and r.json()["error"] == "contact_unavailable" and r.json()["ok"] is False


def test_success_delivers_real_email_over_smtp(make_client, mail_settings, smtp):
    c = make_client(**mail_settings)
    assert c.get("/api/health").json()["contact"] is True
    r = post(c)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert len(smtp.messages) == 1
    msg = email.message_from_bytes(smtp.messages[0].content, policy=policy.default)
    assert msg["To"] == "owner@example.com" and msg["From"] == "site@example.com"
    assert msg["Reply-To"] == "asha@example.org"
    assert msg["Subject"] == "Portfolio message from Asha Rao"
    assert "internship opportunity" in msg.get_content()


def test_delivery_failure_is_never_reported_as_success(make_client, smtp):
    dead_port = smtp.port + 1 if smtp.port < 65000 else smtp.port - 1
    c = make_client(smtp_host="127.0.0.1", smtp_port=dead_port, smtp_security="none",
                    contact_to="o@example.com", contact_from="s@example.com")
    r = post(c)
    assert r.status_code == 502 and r.json()["ok"] is False and r.json()["error"] == "delivery_failed"


def test_validation_messages(make_client, mail_settings, smtp):
    c = make_client(**mail_settings)
    r = post(c, first_name="", email="nope", message="short", consent=False)
    assert r.status_code == 422
    assert set(r.json()["fields"]) == {"first_name", "email", "message", "consent"}
    assert post(c, message="x" * 2001).json()["fields"]["message"].startswith("Shorten")
    assert post(c, first_name="a" * 61).status_code == 422
    assert smtp.messages == []


def test_header_injection_attempts_rejected(make_client, mail_settings, smtp):
    c = make_client(**mail_settings)
    assert post(c, first_name="Bob\r\nBcc: evil@example.com").status_code == 422
    assert post(c, last_name="Rao\nSubject: hacked").status_code == 422
    assert post(c, email="a@example.com\r\nBcc: evil@example.com").status_code == 422
    assert smtp.messages == []


def test_unicode_names_are_accepted(make_client, mail_settings, smtp):
    c = make_client(**mail_settings)
    assert post(c, first_name="Zoë", last_name="Ōtsuka").status_code == 200


def test_honeypot_silently_drops(make_client, mail_settings, smtp):
    c = make_client(**mail_settings)
    assert post(c, website="http://spam.example").json() == {"ok": True}
    assert smtp.messages == []


def test_too_fast_submission_rejected(make_client, mail_settings, smtp):
    c = make_client(**mail_settings)
    r = post(c, elapsed_ms=200)
    assert r.status_code == 400 and r.json()["error"] == "too_fast" and smtp.messages == []


def test_link_spam_rejected(make_client, mail_settings):
    c = make_client(**mail_settings)
    spam = "Buy now http://a.example http://b.example http://c.example please"
    assert post(c, message=spam).status_code == 422


def test_rate_limit(make_client, mail_settings, smtp):
    c = make_client(**mail_settings)
    assert [post(c).status_code for _ in range(5)] == [200] * 5
    r = post(c)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0 and r.json()["error"] == "rate_limited"
    assert len(smtp.messages) == 5


def test_oversized_body_rejected(make_client, mail_settings):
    c = make_client(**mail_settings)
    r = c.post("/api/contact", content=b"x" * 20000, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_wrong_types_return_422_not_500(make_client, mail_settings):
    c = make_client(**mail_settings)
    assert c.post("/api/contact", json={"first_name": ["x"], "elapsed_ms": "soon"}).status_code == 422
    assert c.post("/api/contact", content=b"not json", headers={"content-type": "application/json"}).status_code == 422
