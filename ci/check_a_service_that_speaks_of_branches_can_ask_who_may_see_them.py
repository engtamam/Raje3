"""A service whose API takes a branch must be able to ask WHO MAY SEE THAT BRANCH.

THE DEFECT THIS CLOSES, AND IT WAS LIVE. `campaigns` read `branch_id` straight off the request
body — into the audience resolver and onto the stored campaign the dispatcher re-reads at fire
time — and had no way at all to find out which branch the person pressing the button was allowed
to aim at: no resolver, no call, nothing. So an employee scoped to one branch could send to the
whole establishment, from the owner's message quota and in the owner's name. The isolation did not
merely leak a read; it spent money.

WHY THIS SHAPE AND NOT «EVERY CALL IS NARROWED». The join between a token's `sub` and the branch a
person works in lives in ONE service — `operations` — and every other service must ask for it over
`/internal/operations/branch-scope`. That makes «can this service even ask?» a structural fact a
gate can read honestly. Whether one particular handler narrows correctly is behaviour, and
behaviour is proven by tests that fail when the narrowing is removed (see the campaigns suite).
A gate whose claim is wider than its evidence is the defect family this repo keeps paying for.

NO EXCEPTIONS TABLE. Every service that names a branch at its door either owns the answer or asks
for it. The day one is added that can do neither, the honest fix is to wire the resolver, never to
add a line here.

AND SILENCE IS NOT AGREEMENT: a run that found no service naming a branch has failed to read the
tree, and says so rather than printing OK.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

#: The one door the answer comes through. A service that never says this string cannot ask.
ASKS = "/internal/operations/branch-scope"
#: `operations` owns the staffing rows, so it answers rather than asks.
OWNS = pathlib.Path("app") / "api" / "scope.py"


def names_a_branch(service: pathlib.Path) -> list[pathlib.Path]:
    api = service / "app" / "api"
    if not api.is_dir():
        return []
    return sorted(p for p in api.rglob("*.py")
                  if "__pycache__" not in p.parts and "branch_id" in p.read_text(encoding="utf-8"))


def can_ask(service: pathlib.Path) -> bool:
    app = service / "app"
    if (service / OWNS).is_file():
        return True
    for p in app.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if ASKS in p.read_text(encoding="utf-8"):
            return True
    return False


def main() -> int:
    if not SERVICES.is_dir():
        print("FAIL: no services/ directory — this gate read nothing")
        return 1
    speaking, guilty = [], []
    for service in sorted(p for p in SERVICES.iterdir() if (p / "app").is_dir()):
        files = names_a_branch(service)
        if not files:
            continue
        speaking.append(service.name)
        if not can_ask(service):
            guilty.append((service.name, [str(f.relative_to(ROOT)) for f in files]))
    if not speaking:
        print("FAIL: no service names a branch at its door — the gate read nothing, "
              "and silence is not agreement")
        return 1
    for name, files in guilty:
        print(f"FAIL: `{name}` takes a branch and cannot ask who may see it — "
              f"no {OWNS.as_posix()} and no call to {ASKS}")
        for f in files:
            print(f"       {f}")
    if guilty:
        print("\nWire a branch-scope resolver into the service (see "
              "services/loyalty/app/adapters/branch_scope.py) — do not exempt the service here.")
        return 1
    print(f"{len(speaking)} services name a branch, and every one of them can ask who may see it: "
          + " · ".join(speaking))
    return 0


if __name__ == "__main__":
    sys.exit(main())
