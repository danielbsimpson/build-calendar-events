"""Load and merge configuration from config.yaml and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SMTPConfig:
    host: str = "localhost"
    port: int = 587
    use_tls: bool = True
    username: str | None = None
    password: str | None = None


@dataclass
class EmailConfig:
    to: str = ""
    from_addr: str = ""
    subject_prefix: str = ""
    invite_method: str = "PUBLISH"
    smtp: SMTPConfig = field(default_factory=SMTPConfig)


@dataclass
class EnrichmentConfig:
    fight_card: bool = True
    weather: bool = True
    use_llm: bool = False
    llm_backend: str = "ollama"
    llm_model: str = "llama3"
    llm_endpoint: str = "http://localhost:11434"


@dataclass
class Config:
    look_ahead_days: int = 120
    sources: list[str] = field(default_factory=list)
    data_dir: Path = Path("data")
    store_file: Path = Path("data/sent_events.json")
    email: EmailConfig = field(default_factory=EmailConfig)
    source_options: dict = field(default_factory=dict)
    default_alarms: tuple[int, ...] = (60,)
    event_color: str | None = None
    enrichment: EnrichmentConfig = field(default_factory=EnrichmentConfig)

    def options_for(self, source_name: str) -> dict:
        """Return the per-source options block, or an empty dict."""
        return self.source_options.get(source_name, {})


def load_config(path: str | Path = "config.yaml") -> Config:
    """Load configuration from a YAML file, then apply environment overrides.

    Environment variables (typically from a `.env` file loaded by the shell or
    the caller) take precedence over values in the YAML file for secrets and a
    few common settings.
    """
    path = Path(path)
    raw: dict = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    email_raw = raw.get("email", {}) or {}
    smtp_raw = email_raw.get("smtp", {}) or {}

    smtp = SMTPConfig(
        host=os.getenv("SMTP_HOST", smtp_raw.get("host", "localhost")),
        port=int(os.getenv("SMTP_PORT", smtp_raw.get("port", 587))),
        use_tls=_as_bool(smtp_raw.get("use_tls", True)),
        username=os.getenv("SMTP_USERNAME", smtp_raw.get("username")),
        password=os.getenv("SMTP_PASSWORD", smtp_raw.get("password")),
    )

    email = EmailConfig(
        to=os.getenv("EMAIL_TO", email_raw.get("to", "")),
        from_addr=os.getenv("EMAIL_FROM", email_raw.get("from", "")),
        subject_prefix=email_raw.get("subject_prefix", ""),
        invite_method=str(email_raw.get("invite_method", "PUBLISH")).upper(),
        smtp=smtp,
    )

    enrich_raw = raw.get("enrichment", {}) or {}
    enrichment = EnrichmentConfig(
        fight_card=_as_bool(enrich_raw.get("fight_card", True)),
        weather=_as_bool(enrich_raw.get("weather", True)),
        use_llm=_as_bool(enrich_raw.get("use_llm", False)),
        llm_backend=str(enrich_raw.get("llm_backend", "ollama")),
        llm_model=str(enrich_raw.get("llm_model", "llama3")),
        llm_endpoint=str(enrich_raw.get("llm_endpoint", "http://localhost:11434")),
    )

    return Config(
        look_ahead_days=int(raw.get("look_ahead_days", 120)),
        sources=list(raw.get("sources", [])),
        data_dir=Path(raw.get("data_dir", "data")),
        store_file=Path(raw.get("store_file", "data/sent_events.json")),
        email=email,
        source_options=raw.get("source_options", {}) or {},
        default_alarms=tuple(raw.get("default_alarms", [60]) or ()),
        event_color=raw.get("event_color") or None,
        enrichment=enrichment,
    )


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
