# Poovarasan S: developer portfolio

The original black-and-red portfolio, upgraded with an interactive terminal, live GitHub data, a project explorer, an optional AI assistant and a working contact form. The visual design and all personal content are unchanged. The static site still works with no backend and with JavaScript off.

## What's new

| Feature | Where | Needs a backend? |
|---|---|---|
| Developer terminal (`help about skills projects github contact clear date`) | `assets/js/terminal.js` | No |
| Live GitHub panel (profile, stars, forks, recent activity), cached, with rate-limit/offline fallback | `assets/js/github.js`, `projects.js` | No (public API, no token) |
| Project explorer: search, category/tech filters, sorting, expandable details | `assets/js/projects.js` | No |
| AI assistant | `assets/js/assistant.js`, `backend/app/assistant.py` | **Yes** + Anthropic API key |
| Contact form with server validation, rate limiting, spam checks | `assets/js/contact.js`, `backend/app/contact.py` | **Yes** + SMTP account |
| Custom 404, skip link, labels, focus rings, reduced-motion fixes, strict CSP | `404.html`, `assets/css/features.css`, `backend/app/main.py` | No |

## Project layout

```
index.html              original page (inline CSS kept; inline script moved to assets/js/main.js)
404.html                custom not-found page
assets/photo.webp       your photo
assets/css/features.css new component styles + accessibility fixes
assets/js/              config, util, main (original behaviour, fixed), github, projects, terminal, assistant, contact
assets/js/data.js       GENERATED from data/portfolio.json (do not edit)
data/portfolio.json     single source of truth for terminal, explorer and the AI assistant
scripts/build_data.py   regenerates data.js (`--check` fails if stale)
backend/app/            FastAPI app (serves the site and /api/*)
backend/tests/          API tests (real SMTP sink, mocked AI upstream)
tests/e2e/              Chromium browser tests (Playwright)
.github/workflows/      ci.yml, deploy-pages.yml
Dockerfile, _headers, .env.example
```

## Run locally

**Static only (no backend):** open `index.html`, or `python -m http.server 8080` and visit http://localhost:8080. The terminal, GitHub panel and explorer work. The assistant and contact form report that they are unavailable (the contact form offers an "open in email app" fallback).

**Full stack:**

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env                                   # then fill in what you want (see below)
uvicorn backend.app.main:app --reload                  # http://127.0.0.1:8000
```

The backend serves the site and the API from one origin, so no CORS setup is needed. Only `index.html`, `404.html`, `assets/` and `/api/*` are served; `.env`, `backend/` and `data/` never are.

## Configuration (environment variables)

Nothing here is ever sent to the browser or committed. `.env` is git-ignored.

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Enables the AI assistant (key from console.anthropic.com). Without it, the assistant shows "unavailable". |
| `ASSISTANT_MODEL` | Model id, default `claude-haiku-5-5`. Change it if your account uses a different model. |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `SMTP_SECURITY` | Mail server for the contact form. `SMTP_SECURITY` is `starttls` (587), `ssl` (465) or `none` (local testing only). For Gmail use an app password. |
| `CONTACT_TO` / `CONTACT_FROM` | Recipient (you) and sender address. Replies go to the visitor via `Reply-To`. |
| `ALLOWED_ORIGINS` | Only if the site is hosted on a different origin than the API. |
| `TRUST_PROXY` | `1` only when exactly one trusted reverse proxy is in front, so rate limits see real client IPs. |
| `MIN_FILL_SECONDS`, `ENABLE_DOCS` | Spam timing heuristic (default 2s); `/docs` (default off). |

**External services:** Anthropic Messages API (assistant, billed per use), any SMTP provider (contact), and GitHub's public REST API (called from the visitor's browser, no token, 60 requests/hour per visitor IP, which is why responses are cached for 15 minutes).

## Editing content

Edit `data/portfolio.json`, then run `python scripts/build_data.py`. CI fails if `data.js` is stale. Every project value currently comes from your original page. The optional fields `problem`, `architecture`, `implementation`, `results` and `demo` are shown **only when present**. Add measured results or a live-demo URL only when you can verify them. The hero/summary text in `index.html` is still edited directly.

## Tests

```bash
pip install -r backend/requirements-dev.txt
python -m playwright install chromium
python -m pytest            # API tests + browser tests
```

Browser tests start a real server and a real local SMTP server and mock only third parties (GitHub, Google Fonts). The AI upstream is mocked in the API tests (no key needed).

## Deploy

**Option A, one service (simplest):** deploy the `Dockerfile` to Render, Fly.io, Railway or Cloud Run. Set the environment variables above as secrets. The site and API share one origin. Health check path: `/api/health`.

**Option B, static site + API:**
1. Deploy the backend as in A and set `ALLOWED_ORIGINS=https://<your-pages-origin>`.
2. In GitHub: Settings > Pages > Source: GitHub Actions. Add the repository variable `PORTFOLIO_API_BASE=https://<your-api-host>`.
3. Push to `main`. `deploy-pages.yml` runs the tests, then publishes. On Netlify/Cloudflare Pages use `_headers` (replace `YOUR-API-HOST`). On a GitHub Pages *project* site (`user.github.io/repo/`) the 404 page's `/` links need the repo path.

## Security notes

- The terminal only runs commands from a fixed `Map`; input is never evaluated, shelled out, or inserted as HTML. Feature modules build the DOM with `textContent` only (a test enforces this).
- Strict CSP (`script-src 'self'`) is sent by the backend; there are no inline scripts.
- Contact: server-side validation, header-injection rejection, honeypot, minimum fill time, link-count limit, per-IP rate limit (5/10 min, 20/day), 16 KB body cap. "Message sent" is displayed only after the server confirms SMTP accepted the message.
- Assistant: key stays on the server; answers are grounded in `portfolio.json`; per-IP rate limit (10/min, 60/hour); upstream errors are never forwarded to the browser; answers are labelled AI-generated.
- Rate limits are in-memory per process. With several instances, use your host's edge limits or a shared store.
- No messages are stored. Adding persistence (and, if you choose PostgreSQL, a secured connection) is intentionally left out.
