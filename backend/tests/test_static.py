import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_index_and_assets(make_client):
    c = make_client()
    r = c.get("/")
    assert r.status_code == 200 and "Poovarasan" in r.text
    assert c.get("/assets/photo.webp").headers["content-type"] == "image/webp"
    assert c.get("/assets/js/terminal.js").status_code == 200


def test_security_headers_and_csp(make_client):
    h = make_client().get("/").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "script-src 'self'" in h["content-security-policy"] and "unsafe-inline" not in h["content-security-policy"].split("script-src")[1].split(";")[0]


def test_private_files_are_not_served(make_client):
    c = make_client()
    for path in ["/.env", "/backend/app/main.py", "/backend/app/settings.py", "/data/portfolio.json", "/.git/config", "/README.md", "/../backend/app/main.py"]:
        r = c.get(path)
        assert r.status_code == 404, path
        assert "ANTHROPIC" not in r.text and "def create_app" not in r.text


def test_custom_404_and_json_404_for_api(make_client):
    c = make_client()
    r = c.get("/no/such/page")
    assert r.status_code == 404 and "doesn’t exist" in r.text and "text/html" in r.headers["content-type"]
    r = c.get("/api/nope")
    assert r.status_code == 404 and r.json() == {"ok": False, "error": "not_found"}


def test_docs_disabled_by_default(make_client):
    c = make_client()
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404


def test_cors_only_for_configured_origins(make_client):
    c = make_client(allowed_origins=("https://me.example",))
    ok = c.get("/api/health", headers={"Origin": "https://me.example"})
    bad = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "https://me.example"
    assert "access-control-allow-origin" not in bad.headers


def test_generated_data_js_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_data.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_noscript_fallback_matches_data():
    """The static HTML cards (what no-JS visitors see) must agree with data/portfolio.json."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    data = json.loads((ROOT / "data" / "portfolio.json").read_text(encoding="utf-8"))
    for p in data["projects"]:
        assert p["repo"] in html, p["id"]
        assert p["title"] in html, p["id"]
    assert data["contact"]["email"] in html
    assert not re.search(r"<script>(?!\s*</script>)", html), "inline scripts would break the strict CSP"
