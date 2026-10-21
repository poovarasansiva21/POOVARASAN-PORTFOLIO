"""Contact form: validation, spam heuristics and SMTP delivery."""
from __future__ import annotations

import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Dict

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field

from .settings import Settings

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LINKS = re.compile(r"(https?://|www\.)", re.I)


class ContactIn(BaseModel):
    """Loose types on purpose: friendly messages come from validate_contact(), not pydantic."""
    model_config = ConfigDict(extra="ignore")
    first_name: str = Field("", max_length=200)
    last_name: str = Field("", max_length=200)
    email: str = Field("", max_length=400)
    message: str = Field("", max_length=6000)
    consent: bool = False
    website: str = Field("", max_length=200)  # honeypot: humans never see or fill this
    elapsed_ms: int = Field(0, ge=0, le=86_400_000)


def validate_contact(d: ContactIn) -> Dict[str, str]:
    """Same rules as assets/js/contact.js. Returns {field: message}; empty means valid."""
    errs: Dict[str, str] = {}
    for key, label in (("first_name", "first name"), ("last_name", "last name")):
        v = getattr(d, key).strip()
        if not v:
            errs[key] = f"Enter your {label}."
        elif len(v) > 60:
            errs[key] = f"Keep your {label} under 60 characters."
        elif _CTRL.search(v) or "\n" in v or "\r" in v:
            errs[key] = f"Your {label} contains characters that aren't allowed."
    em = d.email.strip()
    if not em:
        errs["email"] = "Enter your email address."
    else:
        try:
            validate_email(em, check_deliverability=False)
            if len(em) > 254:
                raise EmailNotValidError("too long")
        except EmailNotValidError:
            errs["email"] = "Enter a valid email address, like name@example.com."
    m = d.message.strip()
    if len(m) < 10:
        errs["message"] = "Write at least 10 characters so I know how to help."
    elif len(m) > 2000:
        errs["message"] = f"Shorten your message by {len(m) - 2000} characters (2000 maximum)."
    elif _CTRL.search(m):
        errs["message"] = "Your message contains characters that aren't allowed."
    elif len(_LINKS.findall(m)) > 2:
        errs["message"] = "Please include at most two links."
    if not d.consent:
        errs["consent"] = "Please confirm you're happy to be contacted at this email address."
    return errs


def _header(s: str, n: int = 100) -> str:
    return re.sub(r"\s+", " ", s).strip()[:n]


def build_email(s: Settings, d: ContactIn) -> EmailMessage:
    first, last, email = d.first_name.strip(), d.last_name.strip(), d.email.strip()
    msg = EmailMessage()
    msg["From"] = s.contact_from
    msg["To"] = s.contact_to
    msg["Reply-To"] = email
    msg["Subject"] = _header(f"Portfolio message from {first} {last}")
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg.set_content(f"New message from the portfolio contact form ({when})\n\nName:  {first} {last}\nEmail: {email}\n\n{d.message.strip()}\n")
    return msg


def send_email(s: Settings, msg: EmailMessage) -> None:
    """Blocking SMTP delivery; call from a worker thread. Raises on any failure."""
    ctx = ssl.create_default_context()
    smtp = (smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=10, context=ctx) if s.smtp_security == "ssl"
            else smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10))
    with smtp as c:
        if s.smtp_security == "starttls":
            c.starttls(context=ctx)
        if s.smtp_user:
            c.login(s.smtp_user, s.smtp_password or "")
        refused = c.send_message(msg)
    if refused:
        raise smtplib.SMTPRecipientsRefused(refused)
