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
DECLARED = re.compile(r"""["']path["']\s*:\s*["']((?:/api/v1|/internal)/[^"']*)["']""")

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
        out.update(DECLARED.findall(text))
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
