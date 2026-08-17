#!/usr/bin/env python3
"""A READ THAT MEANT «ALL OF THEM» MUST NOTICE WHEN IT STOPPED EARLY.

THE DEFECT, AND WE HAVE NOW FOUND IT FOUR TIMES IN THREE SERVICES.

`datastore.find()` returns `(rows, cursor)`. The cursor is how it says «there is more». Written
as `rows, _ = await store.find(..., limit=10000)`, the code has asked for at most ten thousand
rows and then reasoned over them as though they were the population — and there is no signal
anywhere when they are not. Not an exception, not a log line, not a short count the caller could
notice. The set is simply smaller than reality and everything downstream is confidently wrong.

WHAT IT COST, EACH TIME, IN THE OWNER'S WORDS:

  · ي-1  the shop's dashboard was computed from its OLDEST five thousand visits, so a busy shop's
         numbers froze at whatever was true the month it crossed the line.
  · ز-5  `_already_reached` — who this campaign has contacted — read the oldest ten thousand. Pass
         ten thousand recipients and the people reached MOST RECENTLY fall out of the exclusion
         set, so they are sent to again, every pass, until the campaign ends. The report counts
         them as `sent` and nothing distinguishes them from new recipients.
  · و-6  the audience for a «win them back» campaign was read as the five thousand customers with
         the MOST RECENT visit — precisely the people who have not gone anywhere. The owner
         concludes his shop loses nobody.

Three different authors, three different services, one shape. Nobody was careless: every one of
those limits is a sensible-looking guard against loading an unbounded result into memory. The
mistake is not the limit. The mistake is throwing away the one value that says the limit was hit.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. A `find()` asking for AT LEAST {THRESHOLD} rows must
bind its cursor to a real name. Below that you are paging for a screen and the cursor belongs to
whoever scrolls; at or above it you meant «everything», and a read that meant everything has to be
able to tell you it stopped.

WHY A THRESHOLD AT ALL, SAID PLAINLY. `limit=20` on a customer list is a page and the caller
genuinely does not care what comes after. `limit=10000` is nobody's page size — it is a number
chosen to be larger than the problem, which is a prediction, and predictions about how big a shop
gets are the thing this codebase keeps getting wrong. The line is drawn at {THRESHOLD} because
that is well above every real page in the product and well below every «surely this is all of
them» we have found.

BINDING IT IS NOT THE SAME AS HANDLING IT, AND THIS GATE KNOWS THAT. `rows, cursor = ...` and then
ignoring `cursor` still passes. That deeper property is not decidable by reading — but naming the
value puts it in front of the author at the moment they choose the limit, which is the moment the
assumption is made. The gate closes the case that IS decidable: a truncation nobody can even see.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# Above every page in the product, below every "surely this is all of them" we have found.
THRESHOLD = 1000


class Visitor(ast.NodeVisitor):
    """Assignments of the form `<targets> = await <...>.find(..., limit=<big>)`."""

    def __init__(self) -> None:
        self.hits: list[tuple[int, int]] = []       # (lineno, limit)

    def visit_Assign(self, node: ast.Assign) -> None:      # noqa: N802
        value = node.value
        if isinstance(value, ast.Await):
            value = value.value
        # `find` AND `_find`. A store wrapper named `_find` hid four of these from the first
        # version of this gate — including `CustomerStore.by_refs`, which reads ten thousand
        # customers NEWEST-FIRST to resolve a set of pseudonyms, and the overdue are by definition
        # the oldest. One underscore was the whole difference between caught and invisible.
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                and value.func.attr in ("find", "_find")):
            return self.generic_visit(node)

        limit = next((kw.value.value for kw in value.keywords
                      if kw.arg == "limit" and isinstance(kw.value, ast.Constant)
                      and isinstance(kw.value.value, int)), None)
        if limit is None or limit < THRESHOLD:
            return self.generic_visit(node)

        # `rows, _ = ...` — the second element is where find() reports that it stopped.
        for target in node.targets:
            if not isinstance(target, ast.Tuple) or len(target.elts) < 2:
                continue
            second = target.elts[1]
            if isinstance(second, ast.Name) and second.id == "_":
                self.hits.append((node.lineno, limit))
        return self.generic_visit(node)


def main() -> int:
    if not SERVICES.is_dir():
        print(f"{C_R}no services/ — this gate checked nothing, and an empty set is not "
              f"agreement{C_N}")
        return 1

    bad: list[str] = []
    checked = 0

    files = [p for p in sorted(SERVICES.rglob("*.py"))
             if "test" not in p.parts and not p.name.startswith("test_")]
    if not files:
        print(f"{C_R}no service source found — either the layout moved or this gate no longer "
              f"matches it, and an empty set is not agreement{C_N}")
        return 1

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        checked += 1
        visitor = Visitor()
        visitor.visit(tree)
        for lineno, limit in visitor.hits:
            bad.append(
                f"{rel}:{lineno}: asks for up to {limit:,} rows and throws away the cursor. That "
                f"limit is not a page size — it is a prediction that {limit:,} is more than this "
                f"shop will ever have, and when it is wrong the code cannot tell: the rows simply "
                f"stop and everything computed from them is confidently incomplete")

    if bad:
        print(f"{C_R}a read that meant everything cannot tell you it stopped{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Bind the cursor and page until it is empty — or narrow the query so the limit "
              "is a page again.")
        return 1

    if checked == 0:
        print(f"{C_R}no files parsed — an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {checked} files, no read above {THRESHOLD:,} rows hides its own "
          f"truncation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
