"""The roles gate — every section reachable, and no role offered one it cannot use.

WHAT THIS CATCHES, and it caught all three the first time it ran:

  a section gated on a READ that half the roles hold while every control inside it needs a WRITE —
  the person opens it, presses, is refused, and learns to distrust the screen;

  a section no seeded role can reach at all, which is a feature that shipped by accident;

  and the owner, who must reach everything: a section he cannot open is one nobody can.

IT DERIVES BOTH SIDES rather than restating either. The capabilities come out of the services'
declared actions, the gating comes out of nav.ts, and the roles come out of the seed file — so a
capability renamed in a service, a `requires` edited in the console, or a capability dropped from a
role all show up here rather than in somebody's shop.
"""
from __future__ import annotations

import ast
import glob
import io
import json
import re
import sys

ROOT = __file__.rsplit("ci", 1)[0]
NAV = ROOT + "apps/console/src/nav.ts"
ROLES = ROOT + "deploy/seed/roles.json"
# THE SAME ROLES, SHIPPED INSIDE THE IMAGE so a signup at three in the morning needs nobody
# present. Two copies of one fact is a real cost, and this is what pays it: a role added to the
# deploy seed and not to the image would mean a shop provisioned today differs from one
# provisioned last week, silently and permanently.
SHIPPED = ROOT + "services/operations/data/roles.seed.json"

# Roles that exist for someone OUTSIDE the shop. They are not measured against the console's
# sections because the console is not their surface — the till company never signs in here.
EXTERNAL = {"partner"}


def capabilities() -> dict[str, str]:
    """action id -> the capability its route enforces, read from every service that declares one."""
    out: dict[str, str] = {}
    for path in sorted(glob.glob(ROOT + "services/*/app/user_actions.py")
                       + glob.glob(ROOT + "platform/services/*/app/user_actions.py")):
        for node in ast.parse(io.open(path, encoding="utf-8").read()).body:
            name = ""
            if isinstance(node, ast.AnnAssign):
                name = getattr(node.target, "id", "")
            elif isinstance(node, ast.Assign) and node.targets:
                name = getattr(node.targets[0], "id", "")
            if name in ("ACTIONS", "USER_ACTIONS"):
                for row in ast.literal_eval(node.value):
                    # First declaration wins: an id is unique WITHIN a service, and the platform
                    # deliberately reuses some across services with the same capability.
                    out.setdefault(row["id"], row["capability"])
    return out


def sections() -> list[tuple[str, list[str]]]:
    """Every nav section and the capabilities it needs.

    ANCHORED ON `requires:`, NOT ON THE SHAPE OF THE LINE. The pattern here used to be
    `{ id: '...', ... requires: [...] }` — it assumed `id` came first in the object literal.
    It does not: every row starts with `service:`. So the regex matched NOTHING, `sections()`
    returned an empty list, every loop below iterated zero times, and the gate printed
    «every section is reachable, and the owner reaches all 0 of them» in green.

    A gate that matches nothing and reports success is worse than no gate: it occupies the slot
    where a real check would go, and the count it prints — «all 0 of them» — is the only evidence
    it was ever broken. Which is why `main()` now refuses an empty result outright.

    So this walks BACKWARD from `requires:` to the `id:` in the same object, in either order, and
    is indifferent to fields being added or reordered.
    """
    text = io.open(NAV, encoding="utf-8").read()
    out: list[tuple[str, list[str]]] = []
    for m in re.finditer(r"requires:\s*\[([^\]]*)\]", text):
        # The object literal this `requires:` belongs to: back to the nearest unmatched `{`.
        start = text.rfind("{", 0, m.start())
        if start < 0:
            continue
        body = text[start:m.end()]
        sid = re.search(r"id:\s*'([^']+)'", body)
        if not sid:
            continue
        out.append((sid.group(1), re.findall(r"'([^']+)'", m.group(1))))
    return out


def main() -> int:
    caps = capabilities()
    roles = {r["name"]: set(r["capabilities"])
             for r in json.load(io.open(ROLES, encoding="utf-8"))["roles"]}
    faults: list[str] = []

    shipped = {r["name"]: r for r in
               json.load(io.open(SHIPPED, encoding="utf-8"))["roles"]}
    for name, held in roles.items():
        if name not in shipped:
            faults.append(f"role {name!r} is in the deploy seed but not in the image — a shop that "
                          f"signs up itself would never get it")
        elif set(shipped[name]["capabilities"]) != held:
            faults.append(f"role {name!r} carries different capabilities in the two seeds — a shop "
                          f"provisioned by signup differs from one provisioned by hand")
    for name in shipped:
        if name not in roles:
            faults.append(f"role {name!r} is shipped in the image but absent from the deploy seed")

    # AN EMPTY READ IS A FAILURE, NOT A PASS — and this line is the whole lesson of the defect
    # above. The regex matched nothing for months; every loop below iterated zero times; no fault
    # could possibly be raised; and the gate printed «the owner reaches all 0 of them» in green.
    # The count was the only evidence, and nobody reads a count on a line that says ✔.
    #
    # So silence is refused outright. A nav with no gated sections is not a state this product can
    # be in — it would mean nothing is reachable by anybody — and if it ever becomes one, the
    # person who made it so should be told rather than congratulated.
    found = sections()
    if not found:
        print("  [31m✘ no nav section carries a `requires:` — either the file moved or this "
              "check no longer matches it. Refusing to report a pass over an empty set.[0m")
        return 1

    for sid, ids in found:
        unknown = [i for i in ids if i not in caps]
        if unknown:
            faults.append(f"«{sid}» is gated on an action nothing declares: {unknown}")
            continue
        needed = {caps[i] for i in ids}
        reachable = [name for name, held in roles.items()
                     if name not in EXTERNAL and needed <= held]
        if not reachable:
            faults.append(f"«{sid}» is reachable by NO role — needs {sorted(needed)}")
        if "owner" not in reachable:
            faults.append(f"«{sid}» is out of the OWNER's reach — needs {sorted(needed)}")

    if faults:
        for f in faults:
            print(f"  \033[31m✘ {f}\033[0m")
        return 1
    print(f"  \033[32m✔ every section is reachable, and the owner reaches all "
          f"{len(sections())} of them\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
