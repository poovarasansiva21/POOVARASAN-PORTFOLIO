"""Configuration from environment variables only. No secrets live in the repository."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

ROOT = Path(__file__).resolve().parents[2]


def _flag(v: Optional[str], default: bool = False) -> bool:
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


def _num(v: Optional[str], default: float) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def _s(v: Optional[str]) -> Optional[str]:
    v = (v or "").strip()
    return v or None


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    # AI assistant
    anthropic_api_key: Optional[str] = None
    anthropic_url: str = "https://api.anthropic.com/v1/messages"
    assistant_model: str = "claude-haiku-5-5"
    # Contact delivery (SMTP)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_security: str = "starttls"  # starttls | ssl | none
    contact_to: Optional[str] = None
    contact_from: Optional[str] = None
    # Web
    allowed_origins: tuple = ()
    trust_proxy: bool = False
    enable_docs: bool = False
    min_fill_seconds: float = 2.0

    @property
    def assistant_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def contact_enabled(self) -> bool:
        return bool(self.smtp_host and self.contact_to and self.contact_from)


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    e = os.environ if env is None else env
    sec = (_s(e.get("SMTP_SECURITY")) or "starttls").lower()
    return Settings(
        anthropic_api_key=_s(e.get("ANTHROPIC_API_KEY")),
        anthropic_url=_s(e.get("ANTHROPIC_API_URL")) or Settings.anthropic_url,
        assistant_model=_s(e.get("ASSISTANT_MODEL")) or Settings.assistant_model,
        smtp_host=_s(e.get("SMTP_HOST")),
        smtp_port=int(_num(e.get("SMTP_PORT"), 587)),
        smtp_user=_s(e.get("SMTP_USER")),
        smtp_password=_s(e.get("SMTP_PASSWORD")),
        smtp_security=sec if sec in {"starttls", "ssl", "none"} else "starttls",
        contact_to=_s(e.get("CONTACT_TO")),
        contact_from=_s(e.get("CONTACT_FROM")),
        allowed_origins=tuple(o.strip().rstrip("/") for o in (e.get("ALLOWED_ORIGINS") or "").split(",") if o.strip()),
        trust_proxy=_flag(e.get("TRUST_PROXY")),
        enable_docs=_flag(e.get("ENABLE_DOCS")),
        min_fill_seconds=_num(e.get("MIN_FILL_SECONDS"), 2.0),
    )
