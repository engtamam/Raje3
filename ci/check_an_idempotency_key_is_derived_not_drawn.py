"""An idempotency key is DERIVED from the occasion. A drawn one protects nothing.

WHAT IT COST (ز-2). `tick.py` read the key off the row and, when the row had never been sent,
fell back to `f"rem_{uuid.uuid4().hex}"`. A row that has never been sent is precisely the case the
key exists for: two replicas winning the claim in the same second each minted a UUID, and the
quota, the notifier and the send log all recognise a repeat BY THE KEY. They were handed two
unrelated keys, so they saw two unrelated sends. The customer read «حان موعد صيانتك» twice in the
same minute and the shop was billed twice by Meta.

THE SHAPE OF THE ILLUSION IS WHAT MAKES THIS WORTH A GATE. A drawn key works perfectly for the
case everyone tests — the sequential retry after a timeout, where the row now HAS a key and the
fallback never runs. It fails only under concurrency, which is the case nobody reproduces locally
and the only case the guard was put there for. So the defence looks present in every test, in
every log, and in the documentation that calls the key «الحزام الذي يشدّ هذا».

WHAT DERIVED MEANS. The key must be a function of the occasion: who, what, and which send of it.
`_send_key` hashes `tenant|subject|service|kind|due_at`, so two replicas racing over the same send
agree by construction, and a genuinely later send differs in `due_at` and correctly earns its own.

RANDOMNESS IS NOT BANNED — IT IS BANNED FROM THIS ONE PARAMETER. A queue job id, a lease token, a
request id and a coupon code are all correctly `uuid4()`: they identify a thing rather than
recognise a repetition of one. This gate reads only what flows into `idempotency_key`.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

#: Ways this fleet draws a value out of nowhere.
DRAWN = ("uuid4", "uuid1", "token_hex", "token_urlsafe", "token_bytes", "randrange",
         "randint", "getrandbits", "choice", "monotonic", "time_ns")


def _draws(node: ast.AST) -> str:
    """The name of the drawn source inside this expression, or ''."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name)
                                                                else "")
            if name in DRAWN:
                return name
    return ""


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
            # What each local name in this function was last assigned — one hop is enough, and it
            # is the hop `key = row.get(...) or uuid4()` hides behind.
            assigned: dict[str, ast.AST] = {}
            for stmt in ast.walk(fn):
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                        and isinstance(stmt.targets[0], ast.Name):
                    assigned[stmt.targets[0].id] = stmt.value

            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                kw = next((k for k in node.keywords
                           if k.arg in ("idempotency_key", "idem_key")), None)
                if kw is None:
                    continue
                checked += 1
                where = kw.value
                drawn = _draws(where)
                if not drawn and isinstance(where, ast.Name) and where.id in assigned:
                    drawn = _draws(assigned[where.id])
                if drawn:
                    hits.append(f"{rel}:{node.lineno}: {fn.name}() passes an idempotency key "
                                f"drawn from {drawn}()")

    if hits:
        print(f"{len(hits)} idempotency key(s) drawn rather than derived:")
        for h in hits:
            print("  " + h)
        print("\nA drawn key works for the sequential retry and fails under concurrency — which is")
        print("the only case it was put there for. Two replicas racing over the same send draw two")
        print("different keys, so the quota, the notifier and the send log see two unrelated sends:")
        print("the customer reads the message twice and the shop is billed twice.")
        print("\nDerive it from the occasion — who, what, and which send of it. See")
        print("services/reminders/app/core/tick.py `_send_key`.")
        return 1

    print(f"{checked} idempotency key(s) passed: every one derived from its occasion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
