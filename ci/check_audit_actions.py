"""Every audited action a route emits must be DECLARED in the same service.

WHY THIS EXISTS, AND IT IS NOT HYPOTHETICAL. The auditor refuses an undeclared action by raising
DeclarationError — write-ahead, before the work happens. So a route that emits an action nobody
declared does not "log less": it returns 500 and PERFORMS NOTHING, for every tenant, permanently.

Three of these were live in this repository at once:

    loyalty.adjusted            «تعديل النقاط» — every points adjustment, every shop
    customer.erasure_requested  the PDPL erasure a customer asked for
    loyalty.redeemed            every redemption arriving from an integrated till

and a fourth (whatsapp.number_registered) was caught only because a test happened to exercise it.
Nothing else would have. The route is correct, the core is correct, the test suite is green — and
the feature is dead the moment it ships.

THIS ONE HAS NO ALLOW-LIST, deliberately. There is no such thing as a legitimately undeclared
action: the platform will refuse it at runtime, so an entry here would only be a note explaining why
we shipped a 500. The check is the declaration and nothing else.

WHAT IT READS. Every `*.record("<literal>", …)` call in a service's app/ — the auditor is reached
under several names (`auditor`, `self._auditor`, `request.app.state.auditor`), so the receiver is
ignored and the method name plus a literal first argument is what identifies the call. A non-literal
action (a variable, an f-string) is REPORTED SEPARATELY rather than passed over, because this check
cannot verify it and silence would read as approval.

    python ci/check_audit_actions.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

# Methods that carry an action name as their first argument. `record` is the auditor's; the others
# are the shapes this fleet has used for the same idea.
RECORD_METHODS = {"record", "record_action", "audit"}

# THE PLATFORM'S OWN VOCABULARY, and checking the name alone is not enough: a declaration carrying
# a `source` outside this set raises the SAME DeclarationError at boot, so a service can be fully
# declared and still refuse every request. Found by writing a declaration with source "machine" —
# which reads perfectly and is not a word the platform knows.
VALID_SOURCES = {"admin", "auth", "internal", "system", "user"}


BAD_SHAPE: list[str] = []


def declared_actions(service: pathlib.Path) -> set[str] | None:
    """What this service says it may audit. `None` means it has no declaration file at all."""
    path = service / "app" / "auditable_actions.py"
    if not path.exists():
        return None
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        # {"action": "x", …} — the shape every service in this repo uses.
        if isinstance(node, ast.Dict):
            entry = {}
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                    entry[key.value] = value.value
            action = entry.get("action")
            if isinstance(action, str):
                out.add(action)
                source = entry.get("source")
                if source is not None and source not in VALID_SOURCES:
                    BAD_SHAPE.append(f"{service.name}: «{action}» declares source "
                                     f"'{source}' — the platform accepts only "
                                     f"{sorted(VALID_SOURCES)}")
        # A bare list of names, in case a service ever writes it that way.
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "." in node.value:
            out.add(node.value)
    return out


def emitted_actions(service: pathlib.Path) -> tuple[list[tuple[str, int, str]], list[tuple[str, int]]]:
    """(literal emissions, unverifiable emissions) across the service's app/."""
    literals: list[tuple[str, int, str]] = []
    dynamic: list[tuple[str, int]] = []
    for path in sorted((service / "app").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:                      # a file that cannot parse is its own bug
            print(f"{C_R}  ✘ {path.relative_to(ROOT)} does not parse: {exc}{C_N}")
            sys.exit(1)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr not in RECORD_METHODS or not node.args:
                continue
            # THE RECEIVER IS IGNORED FOR THE VERDICT, AND READ FOR THE NOISE.
            #
            # `auditor.record`, `self._auditor.record` and `request.app.state.auditor.record` are
            # the same call, and matching the receiver would pass a route that reached the auditor
            # by a new name — so a LITERAL action is checked whatever it was called on.
            #
            # But `record` is an ordinary English word, and this repo uses it for persistence too:
            # `store.record(attempt)` writes a connection row and has nothing to do with the audit
            # log. Those were being counted as «an audited action built at runtime», so the warning
            # list filled with rows that were never audit calls — and a warning list nobody can act
            # on is one people learn to scroll past, which is how the real entries in it get lost.
            #
            # NARROWED BY SCOPE, NEVER BY PATTERN: a non-literal action on something that IS an
            # auditor is still reported, exactly as before.
            receiver = node.func.value
            name = (receiver.id if isinstance(receiver, ast.Name)
                    else receiver.attr if isinstance(receiver, ast.Attribute) else "")
            first = node.args[0]
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                literals.append((rel, node.lineno, first.value))
            elif "audit" in name.lower():
                dynamic.append((rel, node.lineno))
    return literals, dynamic


def main() -> int:
    if not SERVICES.exists():
        print(f"{C_R}  ✘ no services/ directory{C_N}")
        return 1

    missing: list[str] = []
    unverifiable: list[str] = []
    checked = 0

    for service in sorted(p for p in SERVICES.iterdir() if (p / "app").is_dir()):
        declared = declared_actions(service)
        literals, dynamic = emitted_actions(service)
        if declared is None:
            if literals or dynamic:
                missing.append(f"{service.name}: emits audited actions and has NO "
                               f"app/auditable_actions.py at all")
            continue
        checked += 1
        for rel, line, action in literals:
            if action not in declared:
                missing.append(f"{rel}:{line} emits «{action}» — not declared in "
                               f"{service.name}/app/auditable_actions.py")
        for rel, line in dynamic:
            unverifiable.append(f"{rel}:{line}")

    # REPORTED, NEVER SILENT. A computed action name cannot be checked here, and saying nothing
    # about it would let this file claim a coverage it does not have.
    if unverifiable:
        print(f"{C_Y}  ~ {len(unverifiable)} audited action(s) built at runtime — outside this "
              f"check's reach, and each is a place the 500 can still hide:{C_N}")
        for line in unverifiable[:20]:
            print(f"{C_Y}      {line}{C_N}")

    # A DECLARATION THE PLATFORM REJECTS IS THE SAME 500, arriving at boot instead of at the call.
    missing.extend(BAD_SHAPE)

    if missing:
        print(f"{C_R}  ✘ {len(missing)} audited action(s) would refuse at runtime — the route "
              f"returns 500 and performs NOTHING:{C_N}")
        for line in missing:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Declare each in its service's app/auditable_actions.py "
              f"(action · source · critical · resource · why).{C_N}")
        return 1

    print(f"{C_G}  ✔ every audited action is declared in its own service "
          f"({checked} services read){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
