"""InboundFeed adapters. build() picks HttpInboundFeed or NullInboundFeed — see http.py."""
from __future__ import annotations

from app.adapters.inbound_feed.http import HttpInboundFeed, NullInboundFeed, build

__all__ = ["HttpInboundFeed", "NullInboundFeed", "build"]
