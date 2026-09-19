"""The owner's decision: a shift supervisor no longer sees the «محلّي» shop dashboard
(nav.ts `shop` section, gated on the `reminders.today` and `insights.dashboard` action ids,
which require `reminders.read` and `insights.read` respectively). Both capabilities were removed
from `supervisor` in this file and in `deploy/seed/roles.json` together — a CI gate
(ci/check_deploy_wiring.py) already keeps the two files byte-identical, so this test only needs
to read the one that ships inside the image.
"""
from __future__ import annotations

import json
from pathlib import Path

ROLES_SEED = Path(__file__).resolve().parents[2] / "data" / "roles.seed.json"


def _supervisor() -> dict:
    data = json.loads(ROLES_SEED.read_text(encoding="utf-8"))
    for role in data["roles"]:
        if role["name"] == "supervisor":
            return role
    raise AssertionError("no `supervisor` role in roles.seed.json")


def test_supervisor_lacks_reminders_read_and_insights_read():
    caps = set(_supervisor()["capabilities"])
    assert "reminders.read" not in caps
    assert "insights.read" not in caps
