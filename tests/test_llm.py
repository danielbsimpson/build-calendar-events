"""Tests for the optional local-LLM polishing layer (no real network)."""

import requests

from calendar_events.config import EnrichmentConfig
from calendar_events.enrich import llm


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_polish_falls_back_to_facts_on_error(monkeypatch):
    def boom(*_args, **_kwargs):
        raise requests.ConnectionError("no server")

    monkeypatch.setattr(llm.requests, "post", boom)
    cfg = EnrichmentConfig(use_llm=True)
    assert llm.polish("FACTS", cfg) == "FACTS"


def test_ollama_builds_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp({"response": "polished"})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    cfg = EnrichmentConfig(
        use_llm=True,
        llm_backend="ollama",
        llm_model="llama3",
        llm_endpoint="http://localhost:11434",
    )
    assert llm.polish("FACTS", cfg) == "polished"
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"]["model"] == "llama3"
    assert captured["json"]["stream"] is False
    assert "FACTS" in captured["json"]["prompt"]


def test_llamacpp_builds_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp({"content": "polished"})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    cfg = EnrichmentConfig(
        use_llm=True,
        llm_backend="llamacpp",
        llm_endpoint="http://localhost:8080",
    )
    assert llm.polish("FACTS", cfg) == "polished"
    assert captured["url"] == "http://localhost:8080/completion"
    assert captured["json"]["n_predict"] == 200
    assert "FACTS" in captured["json"]["prompt"]
