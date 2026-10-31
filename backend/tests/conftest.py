import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["EMAIL_OUTBOX"] = "true"
os.environ["SMTP_HOST"] = ""
os.environ["SECRET_PEPPER"] = "test-pepper"
os.environ["DOCS_PUBLIC"] = "false"
os.environ["COOKIE_SECURE"] = "false"

import pytest
from app.db import Base, engine
from app.emailer import reset_outbox
from app.limits import reset_limits
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    reset_outbox()
    reset_limits()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def call(client: TestClient, method: str, url: str, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    csrf = client.cookies.get("csrf")
    if csrf and method.lower() != "get":
        headers["X-CSRF-Token"] = csrf
    return getattr(client, method)(url, headers=headers, **kwargs)
