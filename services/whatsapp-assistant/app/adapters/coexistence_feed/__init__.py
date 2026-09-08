"""CoexistenceEchoFeed adapters. build() picks HttpCoexistenceEchoFeed or NullCoexistenceEchoFeed —
see http.py."""
from __future__ import annotations

from app.adapters.coexistence_feed.http import (HttpCoexistenceEchoFeed, NullCoexistenceEchoFeed,
                                                 build)

__all__ = ["HttpCoexistenceEchoFeed", "NullCoexistenceEchoFeed", "build"]
