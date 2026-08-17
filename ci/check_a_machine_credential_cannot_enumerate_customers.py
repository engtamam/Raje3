#!/usr/bin/env python3
"""A ROUTE THAT HANDS A CUSTOMER'S IDENTITY TO A MACHINE IS METERED AGAINST THAT MACHINE'S WORK.

WHAT THIS PREVENTS, AND A RATE LIMIT DOES NOT PREVENT IT.

`GET /till/customer?phone=…` answers with the customer's NAME, his visit count, his points balance
and the rewards he can take. That is the right answer at a counter — a loyalty programme invisible
where the customer is standing is not a programme. It is also, unchanged, an extraction interface:
iterate the phone number space and the same credential returns the shop's entire customer base.

THE PER-WINDOW RATE LIMIT DOES NOT CLOSE THIS. It bounds a burst. A till credential lives for
years and is held by a vendor with five hundred shops behind it; an extractor with patience stays
under any per-minute budget and still walks the whole book. The bound that actually holds is a
RATIO: a till that recorded forty visits today has no business making five thousand lookups today.
Nobody can argue with that shape, it needs no allowlist, and it fails closed.

AND THE OWNER WAS TOLD SOMETHING ELSE. `docs/وصف-منصة-راجع.md` said the till credential carries
«تسجيل الزيارة وحدها» — recording only. That was true when it was written and stopped being true
when the counter was given the balance and the redemption. Two of our own documents disagreed and
the code followed neither exactly, which is how nobody noticed: each reader checked the one that
agreed with them.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. In a module whose routes are guarded by a MACHINE
credential, any handler that returns a customer's identifying fields must pass through the meter.
Not «should be rate limited» — must name the meter, so that adding a second lookup route is a
decision rather than an oversight.

WHY NOT «check the one route». Because the next one — a booking lookup, a receipt reprint, a
loyalty tier check — will be written by somebody solving a real counter problem, and the
enumeration will arrive as a side effect of a feature nobody thought of as a read.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The meter every such handler must go through. Named here so the gate and the code agree on one
# spelling rather than on a regex that drifts.
METER = "count_lookup"

# A module that serves a MACHINE credential rather than a signed-in human. The till is ours today;
# the marker is the client-credentials comment the module carries, not the filename.
FOR_MACHINES = ("client-credentials", "client_credentials", "service account", "machine credential")

# Fields that identify a person. A handler returning any of these is handing over identity, whatever
# the route is called.
IDENTIFYING = ("name", "phone", "plate", "balance", "points")


def _returns_identity(fn: ast.AST) -> bool:
    """Does this handler build a response carrying identifying fields?"""
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if keys & set(IDENTIFYING):
                return True
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if node.slice.value in IDENTIFYING:
                return True
    return False


def _is_route(fn: ast.AST) -> bool:
    for dec in getattr(fn, "decorator_list", []):
        f = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(f, ast.Attribute) and f.attr in ("get", "post", "put", "patch", "delete"):
            return True
    return False


def main() -> int:
    bad: list[str] = []
    checked = 0
    metered = 0

    files = sorted(SERVICES.rglob("*.py"))
    if not files:
        print(f"{C_R}no service modules found — this gate checked nothing, which is not the same "
              f"as finding nothing wrong{C_N}")
        return 1

    for path in files:
        if "test" in path.parts or path.name.startswith("test_"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        low = text.lower()
        if not any(m in low for m in FOR_MACHINES):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            bad.append(f"{rel}: cannot parse it — {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_route(node) or not _returns_identity(node):
                continue
            checked += 1
            body = ast.unparse(node)
            if METER in body:
                metered += 1
                continue
            bad.append(
                f"{rel}:{node.lineno}: `{node.name}` returns a customer's identity to a machine "
                f"credential and never calls `{METER}`. A per-window rate limit bounds a burst; "
                f"it does not stop a patient extractor from walking the whole customer base one "
                f"phone number at a time over months")

    if bad:
        print(f"{C_R}a machine credential can enumerate customers{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  See services/operations/app/core/till_budget.py.")
        return 1

    if checked == 0:
        print(f"{C_R}no machine-facing handler returns customer identity — either they moved or "
              f"this gate no longer matches them, and an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {metered} of {checked} machine-facing identity reads are metered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
