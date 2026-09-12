"""Source base class and a simple name-based registry."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Event

#: Maps a source name (e.g. "ufc") to its Source subclass.
_REGISTRY: dict[str, type["Source"]] = {}


def register(name: str):
    """Class decorator that registers a Source under a given name."""

    def _decorator(cls: type["Source"]) -> type["Source"]:
        cls.name = name
        _REGISTRY[name] = cls
        return cls

    return _decorator


def get_source(name: str, options: dict | None = None) -> "Source":
    """Instantiate a registered source by name."""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown source '{name}'. Registered: {available_sources()}")
    return _REGISTRY[name](options or {})


def available_sources() -> list[str]:
    """Return the names of all registered sources."""
    return sorted(_REGISTRY)


class Source(ABC):
    """Base class for an event source.

    Subclasses implement `fetch()` and are registered with `@register("name")`.
    """

    #: Set by the @register decorator.
    name: str = "base"

    def __init__(self, options: dict | None = None):
        self.options = options or {}

    @abstractmethod
    def fetch(self, look_ahead_days: int) -> list[Event]:
        """Return upcoming events within `look_ahead_days` from now."""
        raise NotImplementedError
