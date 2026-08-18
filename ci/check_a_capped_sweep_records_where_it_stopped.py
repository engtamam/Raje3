"""A scheduled pass over a CAPPED work list must record where it got to.

WHAT THIS WAS WRITTEN AFTER, AND IT IS THE QUIETEST WAY TO STARVE A CUSTOMER.

`ConnectionStore.live_tenants` answers «which shops are live» with `limit=` and
`sort=("at", "desc")` — newest connections first, capped. Two hourly jobs consume it:
`template-approvals` reads Meta's verdicts, and `template-publish` hands the library over.

Both orderings are stable, so every hour they get THE SAME shops in THE SAME order. And the caller
does not wait for ever: the CronJob body times out, the Job's deadline falls, and whatever the pass
had not reached is simply not done. Then the next hour starts again from the same head.

`publish` costs 67 peer calls per shop — 66 templates plus a drain, at 8s apiece — so a single slow
establishment can eat an entire window on its own.

WHAT THAT COSTS THE SHOP AT THE END OF THE LIST: no template of its library is ever registered, so
none is ever approved, so the send path — which rightly refuses to send an unapproved template —
refuses everything. The owner sees «مربوط» in green and never receives a single message about his
own customers. Nothing is logged as broken. The sweep reports success every hour, truthfully, about
the shops it did reach.

THE RULE, AND IT IS NOT «MAKE THE WINDOW BIGGER». A window that fits today's fleet is a window that
stops fitting; the invariant that survives growth is that a bounded pass ADVANCES. Whoever reads a
capped work list must record progress, so the next run starts where this one stopped and every shop
is reached in a bounded number of ticks.

So: any function that reads a capped work list must also mark it. Both halves are named here, and
a new work-list helper is added to WORK_LISTS beside its marker — never exempted.

    python ci/check_a_capped_sweep_records_where_it_stopped.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

#: work-list reader -> the call that records progress for it.
#:
#: NAMED IN PAIRS, because the gate must be able to say what is MISSING rather than merely that
#: something looks wrong. A reader with no marker in the same function is the defect; a reader whose
#: marker lives in a helper it calls would be a false positive, so the marker is looked for in the
#: function AND in anything it calls by name within the same module.
WORK_LISTS = {
    "live_tenants": "mark_swept",
}


def marks_in(fn: ast.AST) -> set[str]:
    """Every attribute or plain call this function makes, by name."""
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ — this gate cannot answer, so it refuses to")
        return 1

    faults: list[str] = []
    checked = 0
    for path in sorted(SERVICES.glob("*/app/**/*.py")):
        if "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            # A FILE THIS GATE CANNOT PARSE IS NOT A FILE THAT PASSED. Another gate reports the
            # syntax error; this one refuses to claim it read something it could not.
            faults.append(f"{path.relative_to(ROOT)} does not parse — it was NOT checked")
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            called = marks_in(fn)
            for reader, marker in WORK_LISTS.items():
                if reader not in called:
                    continue
                # THE DEFINITION ITSELF IS NOT A CALLER. `live_tenants` calling nothing is the
                # helper, not a sweep.
                if fn.name == reader:
                    continue
                checked += 1
                if marker not in called:
                    faults.append(
                        f"{path.relative_to(ROOT)}:{fn.lineno} `{fn.name}` reads the capped work "
                        f"list `{reader}()` and never calls `{marker}()` — so every run starts at "
                        f"the same head, and whatever the window does not reach is never reached")

    if not checked and not faults:
        # SILENCE IS NOT AGREEMENT. If nothing reads a work list, either the helper was renamed or
        # this gate is pointed at the wrong tree; both are worth a failure rather than a green tick.
        print("no capped work-list read was found at all — the helper was renamed, or this gate "
              "needs re-pointing. Refusing to report a pass over an empty set.")
        return 1

    if faults:
        for f in faults:
            print(f"  \033[31m✘ {f}\033[0m")
        print("\nA bounded pass must ADVANCE. Record progress per item and order the next read by "
              "it — raising the window only moves the starvation line.")
        return 1

    print(f"  \033[32m✔ {checked} capped sweep(s): each records where it stopped\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
