"""Two doors to the same act must have the same tail.

WHY THIS EXISTS. A reward redeemed from an integrated till and the same reward redeemed on our own
screen are one act with two entrances. Both called `redeemer.redeem`. But the till route had copied
only ONE of the two things that follow a redemption — the receipt — and not the second: recording a
`service` reward as a visit, which is what restarts the reminder cycle. So a customer who redeemed a
free wash at the counter was reminded days later to come in for the wash he had just had, and the
only place this was visible was the one counter where nobody from the shop is looking at our screen.

The route's own docstring said the two paths «differ only in channel». It was written when that was
true. A tail that is copied rather than called is true exactly once — on the day it is copied.

WHAT IT CHECKS. For every container seam call that appears in more than one route of a service, the
OTHER seams touched by those routes are compared. A seam that one door invokes and the other does
not is reported with both sites. This finds the shape, not the instance: it does not know what
`redeem` means, only that two functions doing the same thing do not agree on what follows it.

Helper calls are expanded one level, so a route that calls a shared `_after_x()` counts as touching
everything that helper touches — which is the whole point: calling the shared tail is how a door
passes this check, and copying half of it is how it fails.

WHAT IT CANNOT SEE, said plainly:
  · a tail reached through two levels of helper (expansion is one level deep);
  · two doors in DIFFERENT services — the near-duplicate lives across a network boundary there, and
    nothing in one repo file can compare them;
  · a seam that is legitimately asymmetric. Those are declared in ASYMMETRIC with the reason, never
    silently skipped, because a list whose entries nobody can justify is a list that grows until the
    check means nothing.

    python ci/check_shared_tail.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# ONLY CONSEQUENCES ARE COMPARED, and this is the line the first version of this file got wrong.
#
# It compared every seam, so two routes that both happened to call `datastore.find` were declared
# «the same act» and 220 differences were reported — a preview and a launch, a list and a create.
# Reads legitimately differ between two doors: one renders a table, the other performs a sale. What
# may NOT differ is what the act LEAVES BEHIND. So the core is a write, the tail is a write, and a
# read is neither.
#
# `datastore` is excluded as a core on purpose: it is the floor every service stands on, not an act.
WRITE_VERBS = ("record", "redeem", "award", "grant", "apply", "consume", "spend", "take",
               "release", "submit", "send", "fire", "publish", "cancel", "revoke", "receipt",
               "schedule", "enqueue", "issue", "refund", "close", "open_request", "erase")
INFRASTRUCTURE = {"datastore", "telemetry", "auditor", "settings", "config", "flags", "store"}


def _is_consequence(seam: str) -> bool:
    holder, verb = seam.split(".", 1)
    return holder not in INFRASTRUCTURE and verb in WRITE_VERBS

# Declared asymmetries: (service, core seam call, seam one door has and the other does not, why).
ASYMMETRIC: set[tuple[str, str, str]] = set()


def _attr_chain(node: ast.AST) -> str:
    """`c.redeemer.redeem(...)` → "redeemer.redeem"; anything else → ""."""
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Attribute):
        return ""
    root = node.value.value
    if not isinstance(root, ast.Name) or root.id not in ("c", "container"):
        return ""
    return f"{node.value.attr}.{node.attr}"


def _seams(fn: ast.AST, helpers: dict[str, ast.AST], depth: int = 1) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        chain = _attr_chain(node.func)
        if chain:
            out.add(chain)
        elif depth and isinstance(node.func, ast.Name) and node.func.id in helpers:
            out |= _seams(helpers[node.func.id], helpers, depth - 1)
    return out


def _is_route(fn: ast.AST) -> bool:
    return any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
               and d.func.attr in ("get", "post", "put", "delete", "patch")
               for d in getattr(fn, "decorator_list", []))


def main() -> int:
    problems: list[str] = []
    compared = 0

    for service in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        routes: dict[str, tuple[str, set[str]]] = {}
        helpers: dict[str, ast.AST] = {}
        trees: list[tuple[str, ast.Module]] = []

        for path in sorted((service / "app" / "api").rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            trees.append((rel, tree))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _is_route(node):
                    helpers[node.name] = node

        for rel, tree in trees:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_route(node):
                    routes[f"{rel}:{node.lineno} {node.name}()"] = (
                        rel, _seams(node, helpers))

        # A core call shared by two or more doors is an act with two entrances.
        core: dict[str, list[str]] = {}
        for where, (_, seams) in routes.items():
            for seam in seams:
                core.setdefault(seam, []).append(where)

        for seam, doors in sorted(core.items()):
            if len(doors) < 2 or not _is_consequence(seam):
                continue
            compared += 1
            tails = {d: {s for s in routes[d][1] if s != seam and _is_consequence(s)}
                     for d in doors}
            union: set[str] = set().union(*tails.values())
            for door, tail in tails.items():
                for missing in sorted(union - tail):
                    if (service.name, seam, missing) in ASYMMETRIC:
                        continue
                    others = [d for d in doors if missing in tails[d]]
                    problems.append(
                        f"{door} calls {seam} but never {missing} — {others[0]} does")

    if problems:
        print(f"{C_R}  ✘ {len(problems)} door(s) performing an act whose tail they do not "
              f"finish:{C_N}")
        for line in sorted(set(problems)):
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Call the shared tail, or declare the asymmetry with its reason. A tail "
              f"that is copied rather than called is true exactly once.{C_N}")
        return 1

    print(f"{C_G}  ✔ every act reached through two doors finishes the same way "
          f"({compared} shared seams){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
