import dataclasses
import socket

import pytest
from aiosmtpd.controller import Controller
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings


class Sink:
    """Real SMTP server on localhost that records what it receives."""
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope)
        return "250 OK"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def smtp():
    sink = Sink()
    port = free_port()
    ctl = Controller(sink, hostname="127.0.0.1", port=port)
    ctl.start()
    sink.port = port
    yield sink
    ctl.stop()


@pytest.fixture()
def make_client():
    clients = []

    def _make(**overrides):
        s = dataclasses.replace(Settings(), **overrides)
        c = TestClient(create_app(s), base_url="http://testserver")
        c.__enter__()
        clients.append(c)
        return c
    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture()
def mail_settings(smtp):
    return dict(smtp_host="127.0.0.1", smtp_port=smtp.port, smtp_security="none",
                contact_to="owner@example.com", contact_from="site@example.com")


GOOD = {"first_name": "Asha", "last_name": "Rao", "email": "asha@example.org",
        "message": "Hi, I'd like to talk about an internship opportunity.", "consent": True,
        "website": "", "elapsed_ms": 9000}
