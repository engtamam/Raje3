#!/usr/bin/env python3
# =============================================================================
# check_product_config.py — fail the build before production does.
#
# config/product.json is the ONE place Raje3's identity lives. This guard proves
# a hand edit did not break it:
#   * it still parses, and matches product.schema.json (structure + patterns);
#   * every FROZEN identifier is present and non-empty (a rename must not drop one);
#   * the product name / slug has NOT leaked into a service name (a leak is exactly
#     what makes a rename a search-and-replace instead of a one-file edit);
#   * locale.default is one of locale.supported, and every rtl locale is too.
#
# Stdlib only. If `jsonschema` is importable it is used for full schema validation;
# otherwise a structural fallback checks the same required shape. Either way the
# semantic checks below always run — they are the ones a schema cannot express.
#
# Exit 0 = clean. Exit 1 = a problem, named on the exact line.
# =============================================================================
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "product.json"
SCHEMA = HERE.parent / "config" / "product.schema.json"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
if not sys.stdout.isatty():
    C_G = C_R = C_Y = C_N = ""

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def load(path: Path) -> dict:
    if not path.exists():
        fail(f"missing file: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.name} is not valid JSON: {exc}")
        return {}


def schema_validate(data: dict, schema: dict) -> None:
    """Full validation when jsonschema is available; structural fallback otherwise."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        for key in schema.get("required", []):
            if key not in data:
                fail(f"schema(required): top-level key '{key}' is missing")
        print(f"{C_Y}  ⚠ jsonschema not installed — ran structural fallback only{C_N}")
        return
    try:
        jsonschema.validate(instance=data, schema=schema)
        print(f"{C_G}  ✔ matches product.schema.json{C_N}")
    except jsonschema.ValidationError as exc:
        loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        fail(f"schema: at '{loc}': {exc.message}")


def semantic_checks(data: dict) -> None:
    identity = data.get("identity", {})
    slug = identity.get("slug", "")
    name_en = (identity.get("nameEn") or "").lower()

    # Frozen identifiers: present and non-empty.
    identifiers = data.get("identifiers", {})
    for key in ("jwtIssuer", "optoutLinkNs", "eventNs", "userAgent"):
        val = identifiers.get(key)
        if not isinstance(val, str) or not val.strip():
            fail(f"identifiers.{key} must be a non-empty string (it is FROZEN — never drop it)")

    # The product name must NOT be baked into a service name — that is the leak
    # that turns a rename into a cross-service search-and-replace.
    leak_tokens = {t for t in (slug.lower(), name_en) if t}
    for svc in data.get("services", {}).get("names", []):
        low = svc.lower()
        for tok in leak_tokens:
            if tok and tok in low:
                fail(f"services.names: '{svc}' embeds the product name '{tok}' — "
                     f"use a neutral domain name (e.g. 'operations', not '{slug}-operations')")

    # locale.default and every rtl entry must be within supported.
    locale = data.get("locale", {})
    supported = set(locale.get("supported", []))
    default = locale.get("default")
    if default and default not in supported:
        fail(f"locale.default '{default}' is not in locale.supported {sorted(supported)}")
    for code in locale.get("rtl", []):
        if code not in supported:
            fail(f"locale.rtl '{code}' is not in locale.supported {sorted(supported)}")


def main() -> int:
    print("▸ checking config/product.json")
    data = load(CONFIG)
    schema = load(SCHEMA)
    if data and schema:
        schema_validate(data, schema)
        semantic_checks(data)

    if errors:
        print(f"\n{C_R}✖ product config invalid:{C_N}")
        for e in errors:
            print(f"{C_R}  • {e}{C_N}")
        return 1
    print(f"{C_G}✔ product config OK{C_N}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
