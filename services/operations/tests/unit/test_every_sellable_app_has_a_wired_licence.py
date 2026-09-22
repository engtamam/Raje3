"""Every key in `core/apps.py::KEYS` must have a REAL container attribute
(`core/apps.py::licence_attr(key)`) built by `build_container()` — not because a hand-written test
enumerates them (that is exactly how `feature.mobile_ai_assistant` slipped through: added to
`APPS` without its own line in `container.py`, a real bug this file's own commit found and fixed),
but because `app/api/subscribed.py::subscribed_write`'s own generic OR-gate (`_ANY_APP`, derived
from the SAME `KEYS`) reads a missing attribute as `None` and, by that gate's own documented
"an unwired licence lets the write through" rule, makes the WHOLE write-gate pass for EVERY shop
the moment even one app's own licence attribute is missing.

SO THIS TEST NEVER NEEDS UPDATING when a new app is added — it walks `KEYS` itself, the same list
`_ANY_APP` is built from, rather than a copy of it that a future PR could forget to extend.
"""
from __future__ import annotations

from app.config import Settings
from app.container import build_container
from app.core.apps import KEYS, licence_attr


def _settings() -> Settings:
    return Settings(_env_file=None, INTERNAL_SERVICE_TOKEN="t" * 40)


def test_every_key_in_apps_py_has_a_real_licence_attribute_on_the_container():
    c = build_container(_settings())
    missing = [key for key in KEYS if getattr(c, licence_attr(key), None) is None]
    assert missing == [], (
        f"these keys are in core/apps.py::APPS but have no matching container licence attribute — "
        f"subscribed_write's own OR-gate reads that as 'licence missing' and lets EVERY write "
        f"through for EVERY shop: {missing}")
