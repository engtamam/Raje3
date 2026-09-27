"""app/user_actions.py — the properties the platform's own safety:user-actions CI gate checks,
run locally too since nothing else in this service's own suite would catch a drift.

  * the list is a pure literal (ast.literal_eval), never a computed value
  * every id is unique
  * every (path, method) exists in this service's own manifest endpoints
  * every declared capability is advertised in this service's own manifest
"""
from __future__ import annotations

import ast
from pathlib import Path

USER_ACTIONS_PATH = Path(__file__).resolve().parents[2] / "app" / "user_actions.py"


def _load_actions() -> list[dict]:
    tree = ast.parse(USER_ACTIONS_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        if target is not None and getattr(target, "id", None) == "USER_ACTIONS":
            return ast.literal_eval(node.value)
    raise AssertionError("USER_ACTIONS not found")


def test_the_list_is_a_pure_literal_with_unique_ids():
    actions = _load_actions()
    assert len(actions) > 0
    ids = [a["id"] for a in actions]
    assert len(ids) == len(set(ids)), "duplicate action id"


def test_every_action_names_a_real_manifest_endpoint():
    import os

    os.environ.setdefault("ENV", "test")
    os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "t" * 40)
    os.environ.setdefault("TOKEN_VERIFIER_DRIVER", "hs256")
    os.environ.setdefault("TOKEN_HS256_SECRET", "h" * 40)
    os.environ.setdefault("TOKEN_ISSUER", "iss")
    os.environ.setdefault("TOKEN_AUDIENCE", "aud")
    os.environ.setdefault("PII_SALT", "s" * 16)
    os.environ.setdefault("AFFILIATE_TENANT", "raje3-affiliates")
    from app.config import get_settings
    from app.manifest import build_manifest

    manifest = build_manifest(get_settings())
    endpoints = {(e["path"], e["method"]) for e in manifest["endpoints"]}
    caps = set(manifest["capabilities"])

    for action in _load_actions():
        assert (action["path"], action["method"]) in endpoints, (
            f"{action['id']}: {action['method']} {action['path']} is not a real manifest route")
        assert action["capability"] in caps, (
            f"{action['id']}: capability {action['capability']!r} is not advertised")
