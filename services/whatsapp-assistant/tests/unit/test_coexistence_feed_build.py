"""coexistence_feed.build() — the local WHATSAPP_COEXISTENCE_ENABLED gate, separate from
notification-service's own storage flag (see http.py's own docstring on why both exist)."""
from __future__ import annotations

from dataclasses import dataclass

from app.adapters.coexistence_feed.http import (HttpCoexistenceEchoFeed, NullCoexistenceEchoFeed,
                                                build)


@dataclass
class _Settings:
    NOTIFICATION_SERVICE_URL: str = "https://notify.internal"
    WHATSAPP_COEXISTENCE_ENABLED: bool = False
    INTERNAL_SERVICE_TOKEN: str = "tok"


def test_disabled_by_default_yields_the_null_feed_even_with_a_url_configured():
    feed = build(_Settings())
    assert isinstance(feed, NullCoexistenceEchoFeed)
    assert feed.configured is False


def test_enabled_with_a_url_yields_the_real_feed():
    feed = build(_Settings(WHATSAPP_COEXISTENCE_ENABLED=True))
    assert isinstance(feed, HttpCoexistenceEchoFeed)
    assert feed.configured is True


def test_enabled_without_a_notification_url_still_yields_the_null_feed():
    feed = build(_Settings(NOTIFICATION_SERVICE_URL="", WHATSAPP_COEXISTENCE_ENABLED=True))
    assert isinstance(feed, NullCoexistenceEchoFeed)
