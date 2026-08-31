"""The three declarations this service publishes must describe the same service.

The manifest says what capabilities exist and what routes are served; admin_actions says what the
panel may render and under which capability; auditable_actions says what may be recorded. Each is
checked against the code by a repo gate, and each of those gates checks a different pair — so the
combination below is what nothing else looks at, and it is where the cheap mistakes live: an action
pointing at a path the manifest does not declare renders a button that 404s, and one naming a
capability the manifest does not advertise renders a button that 403s.

AND THE NEGATIVE ONE, which is the product decision rather than a consistency check: nothing
anywhere declares a way to read a value back.
"""
from __future__ import annotations

import ast
import pathlib
import re

from app.admin_actions import ADMIN_ACTIONS
from app.auditable_actions import AUDITABLE_ACTIONS
from app.config import get_settings
from app.manifest import build_manifest

APP = pathlib.Path(__file__).resolve().parents[2] / "app"


def _manifest() -> dict:
    return build_manifest(get_settings())


def test_every_admin_action_points_at_a_route_the_manifest_declares():
    declared = {(e.get("method", "GET").upper(), e["path"].replace("{}", "*"))
                for e in _manifest()["endpoints"]}
    for a in ADMIN_ACTIONS:
        key = (a["method"].upper(), re.sub(r"\{[^}]+\}", "*", a["path"]))
        assert key in declared, f"{a['id']} names {key}, which the manifest does not declare"


def test_every_admin_action_names_a_capability_the_manifest_advertises():
    caps = set(_manifest()["capabilities"])
    for a in ADMIN_ACTIONS:
        assert a["capability"] in caps, a["id"]


def test_the_capability_is_narrower_than_platform_operations():
    """Reusing `platform.operations` was available and is refused: it is held by operators whose
    job is content, and replacing the key the whole product sends with is not that job."""
    caps = set(_manifest()["capabilities"])
    assert caps == {"platform.secrets_manage"}
    assert "platform.operations" not in caps


def test_the_action_declarations_are_pure_literals():
    """Both repo gates read these with ast.literal_eval and never import them, so a variable or an
    f-string here breaks the gate rather than this file."""
    for name in ("admin_actions.py", "auditable_actions.py"):
        tree = ast.parse((APP / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List,)):
                ast.literal_eval(node.value)


def test_the_only_auditable_action_is_the_write_and_it_is_critical():
    assert len(AUDITABLE_ACTIONS) == 1
    a = AUDITABLE_ACTIONS[0]
    assert a["action"] == "platform.secret_changed"
    assert a["source"] == "admin"
    assert a["critical"] is True
    # `why` is REQUIRED when critical — an action nobody can justify in one line probably is not.
    assert a["why"].strip()


def test_nothing_declares_a_way_to_read_a_value_back():
    """Asserted across every declaration and every route path, so a `secrets.reveal` added later
    fails here whatever file it is added in."""
    ids = {a["id"] for a in ADMIN_ACTIONS}
    assert ids == {"secrets.list", "secrets.update"}
    paths = [e["path"] for e in _manifest()["endpoints"]]
    assert not any(w in p for p in paths for w in ("reveal", "show", "plaintext", "value"))


def test_this_service_declares_no_erasure_target_and_no_backup_collection():
    """Both absences are decisions. Declaring either would enrol this service on a fan-out roster
    as a holder that acknowledges work it never performs — a green ack that means nothing."""
    m = _manifest()
    assert not any(e["path"].startswith("/internal/privacy") for e in m["endpoints"])
    assert not any(e["path"].startswith("/internal/backup") for e in m["endpoints"])
    assert m["backup"]["collections"] == []
    assert m["user_actions"] == []
