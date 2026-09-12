"""Optional local-LLM polishing of assembled event facts (Ollama / llama.cpp).

Disabled by default. When enabled, the deterministic facts assembled by a source
are sent to a local backend, and its prose reply replaces the description. Any
failure falls back to the original deterministic text so a run never breaks.
"""

from __future__ import annotations

import logging

import requests

from .. import http
from ..config import EnrichmentConfig

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = (
    "You are writing a concise calendar event description for a sports fan. "
    "Rewrite the following facts into a short, clear description. Do NOT invent "
    "any names, times, venues, or results that are not present in the facts. "
    "Keep it under 80 words.\n\nFacts:\n{facts}\n\nDescription:"
)


def polish(facts: str, config: EnrichmentConfig) -> str:
    """Return an LLM-polished description, or the original facts on any error."""
    try:
        if config.llm_backend == "llamacpp":
            result = _llamacpp(facts, config)
        else:
            result = _ollama(facts, config)
    except Exception as exc:  # deterministic text is always the fallback
        logger.warning("LLM polish failed (%s); using deterministic text", exc)
        return facts
    return result or facts


def _ollama(facts: str, config: EnrichmentConfig) -> str:
    url = f"{config.llm_endpoint.rstrip('/')}/api/generate"
    payload = {
        "model": config.llm_model,
        "prompt": PROMPT_TEMPLATE.format(facts=facts),
        "stream": False,
    }
    response = requests.post(
        url,
        json=payload,
        headers={"User-Agent": http.USER_AGENT},
        timeout=http.DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return str(response.json().get("response", "")).strip()


def _llamacpp(facts: str, config: EnrichmentConfig) -> str:
    url = f"{config.llm_endpoint.rstrip('/')}/completion"
    payload = {"prompt": PROMPT_TEMPLATE.format(facts=facts), "n_predict": 200}
    response = requests.post(
        url,
        json=payload,
        headers={"User-Agent": http.USER_AGENT},
        timeout=http.DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return str(response.json().get("content", "")).strip()
