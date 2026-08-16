"""A refusal written for a person must survive the trip to that person.

WHY THIS EXISTS. The platform's error handler is CWE-209 by design: it maps a status to a fixed
code and builds the body from that code ALONE. `HTTPException(400, "الرصيد 30 نقطة، والمكافأة 100
— لا يكفي")` reaches the caller as `{"error": "BAD_REQUEST"}`. The sentence is discarded, silently,
in a layer nobody is reading at the time.

So a route that RAISES a refusal has written a sentence for a shop owner and delivered it to a log.
An operator at the counter with a customer waiting sees a generic failure, cannot tell which field
is wrong, retries the same input, and gives up on the visit. A cashier cannot tell an insufficient
balance from a retired reward. Both were live.

THE RULE. A user- or operator-facing route returns its refusal — a JSONResponse or a plain dict
carrying `reason` — and never raises it. Three files already say so in their own comments
(`field.py:101`, `field.py:383`, `v1/loyalty.py:41` «RETURNED, NOT RAISED»), which is how we know
the rule was understood and then not applied two lines later.

WHAT IT CHECKS: a `raise HTTPException(...)` whose message argument is not a bare constant — an
f-string, a `str(exc)`, or a literal containing Arabic. Those are sentences meant for a human.

WHAT IT DOES NOT CHECK, and why:
  · `/internal/*` routes. Their caller is another service, which reads the status code and logs the
    body; there is no person on the other end whose afternoon depends on the wording. A peer that
    needs the sentence is a different problem, and where one does (the till desk) its route is
    treated as user-facing and listed in FACING.
  · 401/403/404. Those carry no detail worth keeping — «not found» is the whole message, and the
    platform's fixed code says it as well as we could.

    python ci/check_refusal_survives.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# Statuses whose body is the whole message. Raising these loses nothing.
NO_SENTENCE = {"HTTP_401_UNAUTHORIZED", "HTTP_403_FORBIDDEN", "HTTP_404_NOT_FOUND",
               "HTTP_405_METHOD_NOT_ALLOWED", "HTTP_429_TOO_MANY_REQUESTS",
               "401", "403", "404", "405", "429"}

# Internal routes whose caller IS a person's screen one hop away — the sentence has to survive them
# too. Each entry names the reader.
FACING: dict[str, str] = {
    "till_redeem": "operations' LoyaltyDesk reads `reason` and prints it on the cashier's screen",
}


def _is_a_sentence(arg: ast.AST) -> bool:
    """A message written for a human, rather than a code."""
    if isinstance(arg, ast.JoinedStr):          # f"..."
        return True
    if isinstance(arg, ast.Call):               # str(exc), f(...)
        return True
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return any("؀" <= ch <= "ۿ" for ch in arg.value)
    if isinstance(arg, ast.BinOp):              # "a" + str(exc)
        return True
    return False


def _status_name(arg: ast.AST) -> str:
    if isinstance(arg, ast.Attribute):
        return arg.attr
    if isinstance(arg, ast.Constant):
        return str(arg.value)
    return ""


def main() -> int:
    problems: list[str] = []
    checked = 0

    for path in sorted(SERVICES.glob("*/app/api/**/*.py")):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        internal_file = "/internal" in rel or rel.endswith("internal.py")

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_route = any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                           and d.func.attr in ("get", "post", "put", "delete", "patch")
                           for d in fn.decorator_list)
            if not is_route:
                continue
            if internal_file and fn.name not in FACING:
                continue
            checked += 1
            for node in ast.walk(fn):
                if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                    continue
                fname = node.exc.func
                name = fname.id if isinstance(fname, ast.Name) else getattr(fname, "attr", "")
                if name != "HTTPException" or len(node.exc.args) < 2:
                    continue
                if _status_name(node.exc.args[0]) in NO_SENTENCE:
                    continue
                if not _is_a_sentence(node.exc.args[1]):
                    continue
                problems.append(
                    f"{rel}:{node.lineno} {fn.name}() RAISES a refusal written for a person — the "
                    f"platform's handler strips `detail` and the reader gets a bare code")

    if problems:
        print(f"{C_R}  ✘ {len(problems)} refusal(s) that never reach the person they were written "
              f"for:{C_N}")
        for line in problems:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Return it — a dict or JSONResponse carrying `reason` — as field.py and "
              f"v1/loyalty.py already do, and say so in a comment where it is easy to forget.{C_N}")
        return 1

    print(f"{C_G}  ✔ every refusal written for a person is returned rather than raised "
          f"({checked} routes){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
