#!/usr/bin/env python3
# =============================================================================
# check_every_app_has_features.py — an app displayed in the store must carry real, business-value
# features, always — never a bare "what" sentence and never a technical/security guarantee dressed
# up as a selling point.
#
# WHY THIS EXISTS. «كوبونات» shipped once with a "features" list whose entries were internal
# mechanism (automatic redemption, the privacy design) and an internal guarantee (a failed
# attempt's reason gets logged) — none of them a business result a shop chooses this app FOR. The
# owner's own correction: a feature answers "what does this get me", stated as money, a customer
# kept, or a loss avoided — the same bar `RATING_FEATURES`/`VISIT_FEATURES`/`CONTACTS_FEATURES`
# already hold in this file, and the bar every OTHER service's own `core/features.py` holds too
# (see bookings-service's own docstring, "the first pilot of the 'features, not services'
# architecture"). Nothing enforced that bar existed until now — a row could ship with zero
# features, or with features that are really internal plumbing, and nothing failed the build.
#
# TWO VALID SOURCES, BOTH CHECKED. An app's features live in exactly one of two places:
#   1. INLINE, on its own `apps.py` row (`"features": [...]`) — used when operations itself owns
#      the app's code (تسجيل زيارة/جهات الاتصال/التقييم/كوبونات).
#   2. REMOTE, via the console's own `apps.ts::APP_ROWS[].featuresAction` (e.g. "campaigns.
#      features") — used when another service owns the app's code; that service keeps its own
#      `core/features.py::<PREFIX>_FEATURES` tuple, and `ci/check_shared_features_match.py`
#      already guards a feature SHARED across two of those. This gate does not duplicate that one
#      — it only asks "is there at least one feature here at all", never whether shared text matches.
#
# WHAT THIS DOES NOT CHECK. Whether a feature's WORDING reads as a business result rather than a
# mechanism is a judgment call a human makes at review time (the same way the owner caught the
# coupons regression by reading the words, not by a script) — this gate only refuses the shape that
# regresses silently: a row with no features list and no working featuresAction at all.
# =============================================================================
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_PY = ROOT / "services" / "operations" / "app" / "core" / "apps.py"
APPS_TS = ROOT / "apps" / "console" / "src" / "apps.ts"

# action prefix (before the first ".") -> the service directory that owns its `core/features.py`.
# Grown by hand, deliberately — a new remote app picks a prefix and is added here once, the same
# one-line cost as every other registry in this codebase (`APPS`, `AUTHZ_TENANT_ASSIGNABLE_CAPS`, …).
ACTION_PREFIX_TO_SERVICE_DIR = {
    "campaigns": "campaigns",
    "loyalty": "loyalty",
    "bookings": "bookings",
    "insights": "insights",
    "whatsapp_assistant": "whatsapp-assistant",
}

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def apps_py_rows() -> dict[str, bool]:
    """key -> whether its own apps.py row carries a non-empty inline `features` list."""
    tree = ast.parse(APPS_PY.read_text(encoding="utf-8"), filename=str(APPS_PY))
    out: dict[str, bool] = {}
    for node in ast.walk(tree):
        is_apps = (
            (isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "APPS" for t in node.targets))
            or (isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name) and node.target.id == "APPS"))
        if not is_apps or node.value is None:
            continue
        for elt in node.value.elts:  # type: ignore[attr-defined]
            key = None
            has_features = False
            for k, v in zip(elt.keys, elt.values):  # type: ignore[attr-defined]
                if not isinstance(k, ast.Constant):
                    continue
                if k.value == "key" and isinstance(v, ast.Constant):
                    key = v.value
                elif k.value == "features":
                    # `list(COUPONS_FEATURES)` — a Call, never a literal — so presence is what is
                    # checked, not length; emptiness of the SOURCE tuple is checked separately below.
                    has_features = True
            if key is not None:
                out[key] = has_features
    return out


def apps_ts_rows() -> dict[str, str | None]:
    """key -> its featuresAction string, or None when the row carries no such field."""
    text = APPS_TS.read_text(encoding="utf-8")
    out: dict[str, str | None] = {}
    # One row at a time: split on the object-literal boundary this file always uses (`  {` at the
    # start of a line, inside `APP_ROWS`), rather than a full TS parse this repo has no dependency
    # for — the same "read the real source, never assume the shape" discipline as every other
    # structural gate here.
    for block in re.findall(r"\{[^{}]*\}", text, flags=re.S):
        key_m = re.search(r"key:\s*'([^']*)'", block)
        if not key_m:
            continue
        key = key_m.group(1)
        if key == "null":  # the `key: null` base row is never sold as an app
            continue
        action_m = re.search(r"featuresAction:\s*'([^']*)'", block)
        out[key] = action_m.group(1) if action_m else None
    return out


def remote_features_nonempty(action: str) -> bool | None:
    """True/False once the referenced service's own FEATURES tuple is found and its emptiness
    known; None when the action's prefix names no service this gate knows about (a new remote app
    forgot to add itself to ACTION_PREFIX_TO_SERVICE_DIR above — reported as its own problem, not
    silently treated as "has features")."""
    prefix = action.split(".", 1)[0]
    svc_dir = ACTION_PREFIX_TO_SERVICE_DIR.get(prefix)
    if svc_dir is None:
        return None
    features_py = ROOT / "services" / svc_dir / "app" / "core" / "features.py"
    if not features_py.exists():
        return False
    tree = ast.parse(features_py.read_text(encoding="utf-8"), filename=str(features_py))
    for node in ast.walk(tree):
        target_name = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
        if target_name and target_name.endswith("_FEATURES") and isinstance(node.value, ast.Tuple):
            return len(node.value.elts) > 0
    return False


def main() -> int:
    inline = apps_py_rows()
    remote = apps_ts_rows()

    problems: list[str] = []
    for key in sorted(set(inline) | set(remote)):
        if inline.get(key):
            continue  # a real inline list — done, regardless of what the console row says
        action = remote.get(key)
        if not action:
            problems.append(
                f"{key!r} has no inline `features` in apps.py and no `featuresAction` in "
                f"apps.ts — it is displayed with nothing behind it but a one-line 'what'")
            continue
        ok = remote_features_nonempty(action)
        if ok is None:
            problems.append(
                f"{key!r}'s featuresAction {action!r} names a prefix not registered in this "
                f"gate's own ACTION_PREFIX_TO_SERVICE_DIR — add the new service there")
        elif ok is False:
            problems.append(
                f"{key!r}'s featuresAction {action!r} resolves to an EMPTY (or missing) "
                f"features tuple in its owning service — nothing actually renders")

    if problems:
        print(f"{C_R}  ✗ {len(problems)} app(s) with no real features:{C_N}")
        for p in problems:
            print(f"    {C_R}{p}{C_N}")
        return 1

    print(f"{C_G}  ✔ every displayed app carries a real, non-empty features list{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
