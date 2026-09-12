"""Tests for the shared resilient HTTP helper (no real network access)."""

import pytest
import requests

from calendar_events import http


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(str(self.status_code))
            err.response = self  # type: ignore[assignment]
            raise err


@pytest.fixture(autouse=True)
def _fast_and_clean(monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda _s: None)
    http._last_request.clear()


def test_get_retries_on_5xx_then_succeeds(monkeypatch):
    responses = [FakeResponse(503), FakeResponse(200, "ok")]
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(http.requests, "get", fake_get)
    resp = http.get("https://example.com/data")
    assert resp.status_code == 200
    assert len(calls) == 2


def test_get_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(
        http.requests, "get", lambda url, headers=None, timeout=None: FakeResponse(500)
    )
    with pytest.raises(requests.HTTPError):
        http.get("https://example.com/data", retries=3)


def test_get_does_not_retry_on_404(monkeypatch):
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(404)

    monkeypatch.setattr(http.requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        http.get("https://example.com/missing")
    assert len(calls) == 1


def test_get_retries_connection_error_then_raises(monkeypatch):
    attempts = []

    def fake_get(url, headers=None, timeout=None):
        attempts.append(url)
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(http.requests, "get", fake_get)
    with pytest.raises(requests.ConnectionError):
        http.get("https://example.com/data", retries=2)
    assert len(attempts) == 2


def test_get_recovers_after_connection_error(monkeypatch):
    seq = [requests.ConnectionError("boom"), FakeResponse(200, "ok")]

    def fake_get(url, headers=None, timeout=None):
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(http.requests, "get", fake_get)
    resp = http.get("https://example.com/data", retries=3)
    assert resp.text == "ok"


def test_throttle_waits_when_called_too_soon(monkeypatch):
    slept = []
    times = iter([100.0, 100.5])
    monkeypatch.setattr(http.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(http.time, "sleep", lambda s: slept.append(s))
    http._last_request["example.com"] = 100.0

    http._throttle("example.com")

    assert slept == [pytest.approx(http.MIN_REQUEST_INTERVAL)]


def test_robots_allows_missing_file(monkeypatch):
    err = requests.HTTPError("404")
    err.response = FakeResponse(404)  # type: ignore[assignment]

    def fake_get(url, **_kw):
        raise err

    monkeypatch.setattr(http, "get", fake_get)
    assert http.robots_allows("https://example.com/page") is True


def test_robots_disallows_on_fetch_error(monkeypatch):
    err = requests.HTTPError("500")
    err.response = FakeResponse(500)  # type: ignore[assignment]

    def fake_get(url, **_kw):
        raise err

    monkeypatch.setattr(http, "get", fake_get)
    assert http.robots_allows("https://example.com/page") is False


def test_robots_respects_disallow_rules(monkeypatch):
    body = "User-agent: *\nDisallow: /private\n"
    monkeypatch.setattr(http, "get", lambda url, **_kw: FakeResponse(200, body))
    assert http.robots_allows("https://example.com/private/x") is False
    assert http.robots_allows("https://example.com/public") is True
