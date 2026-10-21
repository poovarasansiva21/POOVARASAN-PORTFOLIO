"""Browser test fixtures.

Real: uvicorn serving the site + API, a local SMTP server that receives actual mail, Chromium.
Mocked: api.github.com (so tests are deterministic and never spend the rate limit) and Google Fonts.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from aiosmtpd.controller import Controller
from playwright.sync_api import expect, sync_playwright

from backend.tests.conftest import Sink, free_port

ROOT = Path(__file__).resolve().parents[2]
expect.set_options(timeout=8000)
SECRET_ENV = ["ANTHROPIC_API_KEY", "ANTHROPIC_API_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
              "SMTP_SECURITY", "CONTACT_TO", "CONTACT_FROM", "ALLOWED_ORIGINS", "TRUST_PROXY"]


def _start(extra):
    port = free_port()
    env = {**os.environ, **{k: "" for k in SECRET_ENV}, "MIN_FILL_SECONDS": "0.2", **extra}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1).read()
            return proc, url
        except Exception:
            time.sleep(0.15)
    proc.kill()
    raise RuntimeError("server did not start")


@pytest.fixture(scope="session")
def sink():
    s = Sink()
    s.port = free_port()
    ctl = Controller(s, hostname="127.0.0.1", port=s.port)
    ctl.start()
    yield s
    ctl.stop()


@pytest.fixture(scope="session")
def site(sink):
    """Backend with contact delivery configured (real SMTP) and no AI key."""
    proc, url = _start({"SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(sink.port), "SMTP_SECURITY": "none",
                        "CONTACT_TO": "owner@example.com", "CONTACT_FROM": "site@example.com"})
    yield url
    proc.terminate()


@pytest.fixture(scope="session")
def bare():
    """Backend with nothing configured: contact and assistant must report unavailable."""
    proc, url = _start({})
    yield url
    proc.terminate()


@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(pw):
    b = pw.chromium.launch()
    yield b
    b.close()


# ---------------------------------------------------------------- GitHub mock
def _iso(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo(name, stars, forks, lang, days, fork=False):
    u = "poovarasansiva21"
    return {"name": name, "full_name": f"{u}/{name}", "html_url": f"https://github.com/{u}/{name}", "description": f"{name} description from GitHub",
            "language": lang, "stargazers_count": stars, "forks_count": forks, "pushed_at": _iso(days), "fork": fork, "archived": False}


REPOS = [
    _repo("DSA-Traning", 1, 0, "Java", 1),
    _repo("Smart-Traffic-Management-System", 7, 3, "Python", 4),
    _repo("loan-approval-prediction-using-machine-learning", 5, 2, "Jupyter Notebook", 9),  # lower-case: matching is case-insensitive
    _repo("Fleet-Management-System", 2, 1, "JavaScript", 12),
    _repo("MERN-Rental-App", 0, 0, "JavaScript", 20),
    _repo("Bookrecommendation", 3, 0, "Python", 30),
    _repo("someone-elses-project", 99, 50, "Go", 40, fork=True),  # forks must not inflate totals
]
STARS = 1 + 7 + 5 + 2 + 0 + 3
EVENTS = [{"type": "PushEvent", "repo": {"name": "poovarasansiva21/DSA-Traning"}, "created_at": _iso(1), "payload": {}},
          {"type": "CreateEvent", "repo": {"name": "poovarasansiva21/MERN-Rental-App"}, "created_at": _iso(2), "payload": {"ref_type": "branch"}},
          {"type": "IssuesEvent", "repo": {"name": "poovarasansiva21/Fleet-Management-System"}, "created_at": _iso(3), "payload": {"action": "opened"}},
          {"type": "WatchEvent", "repo": {"name": "someone/else"}, "created_at": _iso(4), "payload": {}}]


class GithubMock:
    CORS = {"access-control-allow-origin": "*", "access-control-expose-headers": "X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After"}

    def __init__(self):
        self.mode = "ok"
        self.calls = []
        self.auth_headers = []

    def handle(self, route):
        req = route.request
        self.calls.append(req.url)
        self.auth_headers.append(req.headers.get("authorization"))
        path = req.url.split("api.github.com")[1].split("?")[0]
        if self.mode == "offline":
            return route.abort("internetdisconnected")
        if self.mode == "rate":
            reset = str(int(time.time()) + 3600)
            return route.fulfill(status=403, headers={**self.CORS, "x-ratelimit-remaining": "0", "x-ratelimit-reset": reset},
                                 json={"message": "API rate limit exceeded"})
        if self.mode == "500":
            return route.fulfill(status=500, headers=self.CORS, json={"message": "boom"})
        empty = self.mode == "empty"
        if path.endswith("/events/public"):
            body = [] if empty else EVENTS
        elif path.endswith("/repos"):
            body = [] if empty else REPOS
        else:
            body = {"login": "poovarasansiva21", "name": "Poovarasan S", "public_repos": 0 if empty else 16, "followers": 0 if empty else 4, "html_url": "https://github.com/poovarasansiva21"}
        route.fulfill(status=200, headers=self.CORS, json=body)

    @property
    def api_calls(self):
        return len(self.calls)


@pytest.fixture()
def gh():
    return GithubMock()


@pytest.fixture()
def make_page(browser, gh):
    contexts = []

    def make(**kw):
        kw.setdefault("reduced_motion", "reduce")
        kw.setdefault("viewport", {"width": 1280, "height": 900})
        ctx = browser.new_context(**kw)
        contexts.append(ctx)
        ctx.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=""))
        ctx.route("https://fonts.gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        ctx.route("https://api.github.com/**", gh.handle)
        page = ctx.new_page()
        page.set_default_timeout(8000)
        page.errors, page.dialogs = [], []
        page.on("pageerror", lambda e: page.errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: m.type == "error" and page.errors.append(f"console: {m.text}"))
        page.on("dialog", lambda d: (page.dialogs.append(d.message), d.dismiss()))
        return page

    yield make
    for c in contexts:
        c.close()


@pytest.fixture()
def page(make_page):
    return make_page()
