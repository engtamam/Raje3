"""AN ENGINE NOTHING CALLS — the loudest silence in this codebase, and the one that looks best.

THE FAMILY THIS GATE CLOSES. Over one audit we found: a redemption engine complete to the last
branch that no screen ever invoked; a campaign runner with no button; a commission statement whose
`build()` was called by its own tests and nothing else; a trial-expiry notice, 179 lines, that no
container ever constructed. Every one of them had passing tests, a full docstring, and zero effect
on a single customer. A dead module does not fail — it is simply never asked, and a suite that only
asks it directly agrees that it works.

WHAT «REACHABLE» MEANS HERE. A core module counts as live when something OUTSIDE `core/` imports
it — a route, the container, an adapter, a cron entrypoint — or when a live core module imports it.
That is transitive on purpose: a module imported only by another dead module is dead too, and
counting the import would let a whole dead subtree vouch for itself.

TESTS DO NOT COUNT, AND THAT IS THE WHOLE POINT. A test import is the exact evidence that misleads:
`build()` was imported, exercised and asserted, and no customer's invoice ever contained its number.

IT CHECKS TWO THINGS, because module reachability alone missed the worst instance we had. The
commission statement's module WAS imported — and its `build()` was called by its own tests and by
nothing else, so the number it computed never reached an invoice. So the second half: every public
entry point a core module declares must be named somewhere else in `app/`. A module whose entire
public surface is referenced only by its own definition is a module the product does not use.

WHAT IT CANNOT SEE, stated rather than implied:
  · A function referenced but never actually invoked — a name in a docstring or a dead branch
    reads as a use here. `check_shared_tail` and `check_unwritten_fields` cover parts of that gap.
  · A dynamic import built from a string. There are none today; one added later hides a module
    from this gate, so it is listed here rather than discovered later.
  · Anything under `platform/` — read-only to us, and not ours to declare dead.

DECLARED EXCEPTIONS CARRY A REASON, NOT A NAME. A module parked here without a sentence explaining
what will call it and when is how a gate becomes a formality.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

# ── modules that are legitimately not imported today, each with the reason ──────────────────────
#
# «NOT YET HELD» IS A DATE, NOT A SHRUG. Anything here must name what will call it. A module whose
# reason has expired is a module to delete — see decision #125, where the answer to a 179-line
# dead notice was `git rm`, not an entry in a table like this one.
NOT_YET_CALLED: dict[str, str] = {
    # Imported by name through the platform's own backup machinery, which resolves the manifest
    # rather than importing the module — invisible to an import graph by construction.
    "backup": "driven by the platform's backup runner via backup_manifest, not by our imports",
    "auditable": "the declaration the platform's auditor reads at boot; declared, never called",
}

# Same idea, for the entry-point half: modules whose public names are resolved by the platform
# rather than named in our code.
SURFACE_RESOLVED_ELSEWHERE = {"auditable", "backup"}


def _module_name(path: pathlib.Path) -> str:
    return path.stem


def _imports(path: pathlib.Path) -> set[str]:
    """Every `app.core.X` this file pulls in, however it spells it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod == "app.core" or mod.endswith(".core"):
                # `from app.core import X, Y`
                for alias in node.names:
                    found.add(alias.name)
            elif ".core." in mod or mod.startswith("core."):
                found.add(mod.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if ".core." in alias.name:
                    found.add(alias.name.rsplit(".", 1)[-1])
    return found


def main() -> int:
    problems: list[str] = []

    for app in sorted(SERVICES.glob("*/app")):
        service = app.parent.name
        core = app / "core"
        if not core.is_dir():
            continue
        modules = {_module_name(p) for p in core.glob("*.py") if p.stem != "__init__"}

        # ROOTS: everything in this service that is not core/ and not a test.
        roots: list[pathlib.Path] = [p for p in app.rglob("*.py")
                                     if "core" not in p.relative_to(app).parts
                                     and "__pycache__" not in p.parts]
        live: set[str] = set()
        for r in roots:
            live |= _imports(r) & modules

        # ...then walk the core graph until it stops growing. A module reached only by a dead
        # module stays dead — otherwise a dead subtree vouches for itself.
        changed = True
        while changed:
            changed = False
            for name in sorted(live):
                for reached in _imports(core / f"{name}.py") & modules:
                    if reached not in live:
                        live.add(reached)
                        changed = True

        # ── HALF TWO: a module that IS reachable, whose public surface nothing names ──────────
        #
        # This is the shape that survived the first sweep. `commission.build()` was imported,
        # tested, asserted — and called by nothing that ever produced an invoice. A dead module is
        # noticeable; a live module with a dead entry point looks exactly like a working one.
        texts = {p: p.read_text(encoding="utf-8", errors="ignore")
                 for p in app.rglob("*.py") if "__pycache__" not in p.parts}
        for module_path in sorted(core.glob("*.py")):
            if module_path.stem in SURFACE_RESOLVED_ELSEWHERE or module_path.stem == "__init__":
                continue
            try:
                tree = ast.parse(texts[module_path])
            except (SyntaxError, KeyError):
                continue
            surface = [n.name for n in tree.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                       and not n.name.startswith("_")]
            if not surface:
                continue
            elsewhere = chr(10).join(v for p, v in texts.items() if p != module_path)
            if not any(re.search(rf"\b{re.escape(n)}\b", elsewhere) for n in surface):
                problems.append(
                    f"{service}/app/core/{module_path.stem}.py declares {surface} and NOT ONE of "
                    f"them is named anywhere else in app/ — the module is reachable, its work is "
                    f"not")

        for name in sorted(modules - live):
            if name in NOT_YET_CALLED:
                continue
            problems.append(
                f"{service}/app/core/{name}.py is imported by nothing outside core/ — "
                f"it cannot run, cannot fail, and its tests prove only that it would work "
                f"if anything asked it")

    if problems:
        print(f"  x {len(problems)} core module(s) the product cannot reach:")
        for line in problems:
            print(f"    {line}")
        print("    Wire it to the screen or the route that was supposed to call it, "
              "or delete it — a module kept 'for later' is a promise the product does not keep.")
        return 1

    print("  + every core module is reachable from a route, a container or an adapter — "
          "no engine is waiting to be called")
    return 0


if __name__ == "__main__":
    sys.exit(main())
