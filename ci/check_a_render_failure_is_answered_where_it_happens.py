"""A message that cannot be built must be ANSWERED — not thrown into the generic failure path.

WHAT THIS WAS WRITTEN AFTER, AND IT IS WHY #371 WAS INVISIBLE FOR MONTHS.

`core/rendering.py` raises `RenderError` for every reason a message cannot be composed: no active
template of this type, a template Meta has not approved, a numbering gap, an owner's text that
breaks a rule — and, since the customer page was switched off, «عنوان الموقع العام غير مضبوط», the
one that currently kills all 36 service wordings.

THE CAMPAIGN PATH CAUGHT IT. The visit path did not. So on the visit path the exception left
`_one()` entirely and landed in the batch's `except Exception`, which calls `_fail()` — and
`_fail` is written for a PEER BEING BRIEFLY UNAVAILABLE: back to pending, due in an hour, retry
for ever. Nothing is written to the send log, because nothing was attempted as far as the log is
concerned.

The result on a live cluster: every visit confirmation in the fleet failing every hour, for ever,
with no row on any screen, no closed schedule, and an owner who sees a product that simply never
messages anybody. The one number that moved was `res.failed`, which no screen reads.

THE RULE. `choose` and `render` are the two calls that raise `RenderError`, and every one of them
must sit inside a `try` whose handler NAMES `RenderError`. Catching it where it happens is what
lets the caller decide the honest thing — record it, close the row, tell somebody — instead of
letting a permanent content failure be retried as though it were a network blip.

WHAT THIS DOES NOT CHECK: what the handler then does. That is a judgement per call site — the
preview shows the sentence, the send path logs and closes. This gate only refuses the case where
nobody is listening at all.

    python ci/check_a_render_failure_is_answered_where_it_happens.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

#: The two calls that raise it. Named by ATTRIBUTE, so `R.render(...)`, `rendering.render(...)`
#: and any other alias of the module are all read the same way — this repository imports it as `R`
#: today and that is not a fact worth encoding.
RAISERS = {"render", "choose"}


def _handles_render_error(handler: ast.ExceptHandler) -> bool:
    """Does this `except` name RenderError — by any of the spellings we use?"""
    names: list[ast.expr] = []
    if handler.type is None:
        # A BARE `except:` IS NOT AN ANSWER. It catches the render failure along with everything
        # else, which is precisely how this one was lost: swallowed by a handler written for a
        # different problem and treated as that problem.
        return False
    if isinstance(handler.type, ast.Tuple):
        names.extend(handler.type.elts)
    else:
        names.append(handler.type)
    for node in names:
        if isinstance(node, ast.Attribute) and node.attr == "RenderError":
            return True
        if isinstance(node, ast.Name) and node.id == "RenderError":
            return True
    return False


def main() -> int:
    if not SERVICES.is_dir():
        print("services/ is missing — this gate cannot answer, and that is not a pass")
        return 1

    bad: list[str] = []
    checked = 0
    for path in sorted(SERVICES.rglob("*.py")):
        posix = path.as_posix()
        if "/tests/" in posix:
            continue
        if "/.venv/" in posix or "/site-packages/" in posix:
            # NOT AN EXEMPTION — A SCOPE. Vendored libraries have their own `render()` that raises
            # their own exceptions; they are not this product's code and no fix of ours reaches
            # them. Narrowing WHERE the rule is asked is allowed; narrowing WHICH of our own call
            # sites must obey it is the exceptions table this repository does not keep.
            continue
        text = path.read_text(encoding="utf-8")
        if "rendering" not in text:
            # THE RULE IS ABOUT OUR RENDERER. A file that never imports `core.rendering` cannot
            # raise `RenderError`, whatever its own `.render()` calls do.
            continue
        tree = ast.parse(text)

        # THE GUARDED SPANS FIRST: the line range of every `try` body whose handlers name
        # RenderError. A call is answered when it falls inside one of them.
        guarded: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) and any(_handles_render_error(h) for h in node.handlers):
                body = node.body
                guarded.append((body[0].lineno, max(getattr(n, "end_lineno", n.lineno)
                                                    for n in body)))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not isinstance(fn, ast.Attribute) or fn.attr not in RAISERS:
                continue
            if not isinstance(fn.value, ast.Name):
                # `self.render(...)` and the like are not the module's function.
                continue
            checked += 1
            line = node.lineno
            if not any(lo <= line <= hi for lo, hi in guarded):
                bad.append(f"{path.relative_to(ROOT)}:{line}: {fn.value.id}.{fn.attr}(…)")

    if bad:
        print("  \033[31m✘ a message that cannot be built is thrown where nobody is listening:"
              "\033[0m")
        for line in bad:
            print(f"      \033[31m{line}\033[0m")
        print("\n    Wrap it in a try whose except names RenderError, and answer it there: record "
              "the row,\n    close the schedule, say the sentence. A permanent content failure "
              "retried as a network blip\n    is a message that never arrives and never appears. "
              "Do not exempt it here.")
        return 1

    print(f"  \033[32m✔ every render/choose is answered where it happens ({checked} call "
          f"site(s))\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
