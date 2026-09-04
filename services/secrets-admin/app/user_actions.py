"""secrets-admin — end-user actions for the platform app catalog.

Deliberately empty: secrets-admin has no self-service surface, only the two operator actions
admin_actions.py declares. See UNDECLARED_ROUTES below for the one route that exists but is
intentionally kept out of both catalogs.
"""
from __future__ import annotations

from typing import Any

USER_ACTIONS: list[dict[str, Any]] = []

# THE PLATFORM'S OWN MECHANISM (see operations/app/user_actions.py, the first to use it).
UNDECLARED_ROUTES: list[dict[str, str]] = [
    {"method": "GET", "path": "/api/v1/secrets/whoami",
     "why": "admin_actions.py's own module docstring is the reason: TWO ACTIONS, AND THERE WILL "
            "NEVER BE A THIRD — this file's test_declarations_agree.py::"
            "test_nothing_declares_a_way_to_read_a_value_back hardcodes that exact set. whoami is "
            "wired for the gateway (see api/v1/__init__.py) but stays outside the admin-action "
            "catalog by the same deliberate-minimalism doctrine that keeps secrets.reveal from "
            "ever existing"},
]
