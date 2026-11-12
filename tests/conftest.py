import json

import pytest
import requests

from listonic_mcp import app
from listonic_mcp.client import ListonicClient


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


class FakeApi:
    """Records every HTTP call; replies come from a queue, default 200 + []."""

    def __init__(self):
        self.calls: list[dict] = []
        self.replies: list[FakeResponse] = []

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.replies.pop(0) if self.replies else FakeResponse(200, [])

    def requests(self):
        """API calls only (no login), as (method, path, json) tuples."""
        return [
            (c["method"], c["url"].removeprefix("https://api.listonic.com/api"), c.get("json"))
            for c in self.calls if "loginextended" not in c["url"]
        ]


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr("listonic_mcp.client.requests.request", fake)
    monkeypatch.setattr(
        "listonic_mcp.client.requests.post",
        lambda url, **kw: (fake.calls.append({"method": "POST", "url": url, **kw})
                           or FakeResponse(200, {"access_token": "tok"})),
    )
    return fake


@pytest.fixture
def client(api):
    c = ListonicClient("me@example.com", "pw", list_id="42")
    app.set_client(c)
    yield c
    app.set_client(None)
