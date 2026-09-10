"""Making the platform's OWN WhatsApp templates ready without anybody typing them — the same
question the owner asked about the shop library ("ليه ما تسوي القوالب جاهزة مع نصوص القوالب
الاخرى؟"), answered the same way: a seed file, read once, registered automatically. Content is
ready; SENDING it for Meta's review is not — that half stays the operator's own explicit click.

WHY THIS IS SEPARATE FROM `library.py`'s SHOP-CONNECT PATH, not a second caller of `publish()`.
`publish()` registers AND drains (submits to Meta) in the same pass — correct for a shop, whose own
consent to connect WhatsApp already covers sending its library for review. The platform's own
templates are sent from OUR number, about OUR business (subscription renewal, low AI-wallet
balance, ...), and the owner decided (2026-09-10) that submitting one is a decision made once, by a
human, from the console — never automatic, at install or at any later boot. `register()` alone
(a local upsert, no Meta call, no cap — see library.py's own docstring) costs nothing and needs no
live Meta connection, so THAT half can run unattended; `drain()` is never called from here.

NEVER RE-REGISTERS A NAME THAT ALREADY EXISTS. `register()` is an upsert: calling it again with the
seed's own content would silently REVERT an operator's own edit (a rewritten body, a fixed
category) back to whatever this file says, and reset an already-approved template to pending in
the process (see notification-service's own register() docstring on why a changed body re-opens
review). So this only ever registers a name `list_names()` has not already seen for `_platform` —
an operator's own work here is never overwritten by a later boot, the same guarantee
`templates.seed_from_file`'s own "applied ONLY when empty" comment in main.py already gives the
shop-library seed, just checked per-name instead of per-table.

`list_names()` returning `None` (could not ask — no list path configured, or the peer unreachable)
refuses to register ANYTHING this pass, rather than reading "could not check" as "nothing exists
yet" and re-registering over content it never actually looked at.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

from app.core.flows import PLATFORM


def load_seed(path: str) -> list[dict[str, Any]]:
    """The platform's own template rows, or `[]` for no file / an unreadable one — a missing seed
    is a quiet no-op here, same posture `library.py`'s own `_variable_examples` takes: a fresh
    install with no file configured yet still boots and serves every other route."""
    if not path:
        return []
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [t for t in (data.get("templates") or []) if isinstance(t, dict) and t.get("name")]


async def seed_platform_templates(library: Any, *, seed_path: str) -> dict[str, int]:
    """Register every seed row `_platform` does not already have. Returns counts for the boot log
    — never raises: a peer hiccup here must not stop the service from serving every other route
    (same "a failure here is LOGGED, not fatal" posture app/main.py's own lifespan comment already
    holds for the shop-library seed)."""
    rows = load_seed(seed_path)
    if not rows:
        return {"registered": 0, "skipped": 0, "failed": 0}
    existing = await library.list_names(PLATFORM)
    if existing is None:
        # COULD NOT ASK — refuse to register anything rather than guess "nothing exists yet" and
        # risk reverting an operator's own edit that this pass simply could not see.
        return {"registered": 0, "skipped": 0, "failed": 0}
    registered = skipped = failed = 0
    for row in rows:
        name = str(row.get("name", ""))
        if name in existing:
            skipped += 1
            continue
        if await library.register(PLATFORM, row):
            registered += 1
        else:
            failed += 1
    return {"registered": registered, "skipped": skipped, "failed": failed}
