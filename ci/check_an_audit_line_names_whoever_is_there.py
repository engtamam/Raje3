"""A route that HAS a person must name that person in its audit line — never a service.

WHAT IT COST (ب-5). `POST /platform/template-help/{name}/answer` wrote `actor="platform"`. That
route is the one where WE answer a shop's «ساعدوني»: an owner presses it when Meta refuses his
template, and our answer is what he then edits into a sentence a thousand of his customers
receive. Every sibling route in the same file names `principal.subject`; this one named the
fleet. So the only question the audit trail exists to answer — «من قال هذا؟» — came back «المنصة»,
which is every one of us and therefore nobody. The route did not even take a `Principal` to name
one from, so the omission could not be spotted by reading the call alone.

THE RULE IS NOT «NEVER USE A LITERAL», AND THAT DISTINCTION IS THE WHOLE GATE. Plenty of audit
lines in this fleet are correctly written by a machine: `actor="playbook"` on the reconcile route,
`actor="schedule"` when the monthly statements are issued, `actor="cron:whatsapp-health"` when a
connection is found dead. Nobody pressed those. Naming a person there would be a lie in the other
direction, and banning the literal would force one.

So the rule is about AVAILABILITY: if the function that writes the line has a `Principal` in its
signature, a person is standing there and the line must say who. If it has none, the action is the
machine's and a literal naming that machine is the honest answer.

A gate that banned the literal outright would be wrong about eight correct lines to catch one
wrong one — and a gate wrong about most of its hits is a gate people learn to scroll past.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"


def _principal_params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names in this signature annotated `Principal` — the people this route already holds."""
    out: set[str] = set()
    args = fn.args
    for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        ann = a.annotation
        if ann is None:
            continue
        text = ast.unparse(ann)
        if "Principal" in text:
            out.add(a.arg)
    return out


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def main() -> int:
    if not SERVICES.is_dir():
        # A GATE THAT CANNOT READ MUST FAIL LOUDLY.
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = [f for f in sorted(SERVICES.rglob("*.py")) if "tests" not in f.parts]
    if not files:
        # SILENCE IS NOT AGREEMENT.
        print("no service source found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    checked = 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            print(f"cannot read {rel}: {exc}")
            return 1

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            people = _principal_params(fn)
            if not people:
                continue                    # the machine's own action; a literal is the truth
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                actor = next((k for k in node.keywords if k.arg == "actor"), None)
                if actor is None:
                    continue
                checked += 1
                # Derived from the principal in any shape — `principal.subject`, `_actor(principal)`,
                # `getattr(principal, "subject", "")`. What it must not be is a constant.
                if _names_in(actor.value) & people:
                    continue
                if isinstance(actor.value, ast.Constant):
                    hits.append(f"{rel}:{node.lineno}: {fn.name}() holds a Principal and writes "
                                f"actor={actor.value.value!r}")

    if hits:
        print(f"{len(hits)} audit line(s) name a service where a person was standing:")
        for h in hits:
            print("  " + h)
        print("\nThe route already has the Principal. Write `actor=principal.subject`, or whatever")
        print("this service's `_actor()` helper returns — «من فعل هذا؟» must not answer «المنصة».")
        print("\nA machine's own action is different and keeps its literal: a route with no")
        print("Principal in its signature is not checked here at all.")
        return 1

    print(f"{checked} audit line(s) written where a person was present: every one names them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
