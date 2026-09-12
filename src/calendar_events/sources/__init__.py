"""Source registry.

Importing this package imports each source module so its `@register`
decorator runs and populates the registry.
"""

from __future__ import annotations

from .base import Source, available_sources, get_source, register  # noqa: F401

# Import concrete sources for their registration side effects.
from . import f1  # noqa: F401,E402
from . import ufc  # noqa: F401,E402

__all__ = ["Source", "available_sources", "get_source", "register"]
