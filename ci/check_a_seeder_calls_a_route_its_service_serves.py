"""A deploy script must not call a platform route that does not exist.

WHAT IT COST. `seed-backup-targets.sh` registered every service with backup-service by PUTting to
`/api/v1/backup/targets`. The route had moved under `operator/`, so all twenty registrations
answered 404 — and the fleet finished every install with ZERO backup targets. The installer
printed a warning, the cluster came up, every pod was green, and the nightly backup ran against
nothing at all. «Nothing is being archived» is not a sentence anybody read; what they read was one
amber line in a hundred lines of success.

WHY A GATE AND NOT CARE. The vendored `platform/` is the authority on its own routes and it moves
between releases. A script that names a path is making a claim about somebody else's code, and the
only moment that claim is currently tested is a real install against a real cluster — which is the
most expensive place to discover it and the one where half a fleet is already changed.

`ci/check_deploy_wiring.py` already does this for CRON paths in values files. This is the same
question asked of the other half: the seeds.

SCOPE. Only `/api/v1/...` and `/internal/...` paths in `deploy/seed/`, matched against the routes
the vendored services actually declare. A path with a `{placeholder}` matches by its literal
prefix, because that is all a static reader can honestly claim.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEEDS = ROOT / "deploy" / "seed"
PLATFORM = ROOT / "platform" / "services"
OURS = ROOT / "services"

#: A quoted path in a script: "/api/v1/…" or "/internal/…".
CALLED = re.compile(r"""["']((?:/api/v1|/internal)/[A-Za-z0-9_\-/{}]+)["']""")

#: TWO WAYS A ROUTE IS DECLARED HERE, AND THE FIRST VERSION OF THIS GATE READ ONE. Besides the
#: decorator, every service publishes an ACTION CATALOGUE (`admin_actions.py`, `user_actions.py`)
#: whose entries carry a full `"path"` — and the console builds its whole navigation from it. Read
#: only the decorators and four correct seeder calls are reported as broken, which is how a gate
#: teaches people to ignore it.
#:
#: AND IT READ THEM OUT OF PROSE, WHICH IS WORSE THAN READING TOO LITTLE. Every action file opens
#: with a docstring showing the schema shape, and that example carries `"path": "/api/v1/things/{id}"`.
#: A regex over raw text ingested it, so `/api/v1/things/…` counted as a route this fleet serves —
#: and a seeder calling it would have passed the gate whose entire job is to catch exactly that.
#: A gate that accepts documentation as evidence is a gate that answers about the comments.
#:
#: So the catalogue is read with the PARSER: `ast.literal_eval` over the module's list assignments,
#: which is how the CI action-schema check reads these files too, and which cannot see a docstring
#: at all. The regex below survives only for non-Python callers of `_paths_in`.
DECLARED = re.compile(r"""["']path["']\s*:\s*["']((?:/api/v1|/internal)/[^"']*)["']""")


def _declared_paths(tree: ast.Module) -> set[str]:
    """Every `path` in an action catalogue, taken from the parsed literal rather than the text."""
    out: set[str] = set()
    # BOTH SPELLINGS OF AN ASSIGNMENT. `ACTIONS = [...]` is an `Assign`; `ACTIONS: list[dict] =
    # [...]` — which is how notification-service writes it — is an `AnnAssign`, a different node
    # entirely. Reading only the first found nothing in that file and reported four correct seeder
    # calls as broken, which is the same false alarm this gate was widened to stop making.
    for node in ast.walk(tree):
        value = getattr(node, "value", None)
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or not isinstance(
                value, (ast.List, ast.Tuple)):
            continue
        try:
            entries = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                path = entry.get("path")
                if isinstance(path, str) and path.startswith(("/api/v1", "/internal")):
                    out.add(path)
    return out

#: How a FastAPI route declares itself, and the prefix its router was mounted under.
ROUTE = re.compile(r"""@router\.(get|post|put|patch|delete)\(\s*["']([^"']*)["']""")
PREFIX = re.compile(r"""APIRouter\([^)]*prefix\s*=\s*["']([^"']*)["']""")
INCLUDE = re.compile(r"""include_router\([^)]*prefix\s*=\s*["']([^"']*)["']""")


def _served() -> set[str]:
    """Every route path the vendored services declare, as a set of literal prefixes."""
    out: set[str] = set()
    trees = [t for t in (PLATFORM, OURS) if t.is_dir()]
    for f in [f for t in trees for f in t.rglob("*.py")]:
        if "test" in f.parts:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            out.update(_declared_paths(ast.parse(text)))
        except SyntaxError:
            # Not our Python to fix — and a file we cannot parse contributes no routes, which is
            # the safe direction here: it can only make this gate report MORE, never less.
            pass
        prefixes = PREFIX.findall(text) + INCLUDE.findall(text)
        for _method, path in ROUTE.findall(text):
            for pre in prefixes or [""]:
                full = (pre + path) or path
                # Routers are mounted again at the app level under /api/v1 or /internal; a static
                # reader cannot follow every mount, so both spellings are accepted as served.
                out.add(full)
                out.add("/api/v1" + full)
                out.add("/internal" + full)
    return out


def _literal(path: str) -> str:
    """The part before any `{placeholder}` — all a static reader can honestly compare."""
    return path.split("{", 1)[0].rstrip("/")


def main() -> int:
    if not PLATFORM.is_dir():
        # A GATE THAT CANNOT READ MUST FAIL LOUDLY: without the submodule it would pass everything.
        print("platform/services is not checked out — this gate cannot answer, so it refuses to")
        return 1
    served = {_literal(p) for p in _served()}
    if not served:
        print("read no routes from platform/ — this gate needs re-pointing")
        return 1

    files = sorted(list(SEEDS.rglob("*.sh")) + list(SEEDS.rglob("*.py")))
    if not files:
        print("no seed scripts found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    checked = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        for line_no, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for path in CALLED.findall(line):
                lit = _literal(path)
                if not lit:
                    continue
                checked += 1
                if lit not in served:
                    hits.append(f"{f.relative_to(ROOT).as_posix()}:{line_no}: {path}")

    if hits:
        print(f"{len(hits)} call(s) to a route no vendored service serves:")
        for line in hits:
            print("  " + line)
        print("\nThe install answers 404, prints a warning, and finishes green — with the thing "
              "that call was supposed to arrange never arranged.")
        return 1
    print(f"{checked} seed calls: every one names a route the platform serves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
