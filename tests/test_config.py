"""Tests for enrichment configuration parsing."""

from calendar_events.config import load_config


def test_enrichment_defaults_when_absent(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("sources:\n  - f1\n", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.enrichment.fight_card is True
    assert cfg.enrichment.weather is True
    assert cfg.enrichment.use_llm is False
    assert cfg.enrichment.llm_backend == "ollama"
    assert cfg.enrichment.llm_model == "llama3"


def test_enrichment_overrides(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "sources:\n  - f1\n"
        "enrichment:\n"
        "  fight_card: false\n"
        "  weather: false\n"
        "  use_llm: true\n"
        "  llm_backend: llamacpp\n"
        "  llm_model: mistral\n"
        "  llm_endpoint: http://localhost:8080\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.enrichment.fight_card is False
    assert cfg.enrichment.weather is False
    assert cfg.enrichment.use_llm is True
    assert cfg.enrichment.llm_backend == "llamacpp"
    assert cfg.enrichment.llm_model == "mistral"
    assert cfg.enrichment.llm_endpoint == "http://localhost:8080"
