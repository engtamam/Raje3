"""Four files list who may fill a template blank. They are one list, or they are a trap.

WHAT THIS CAUGHT. Adding two fill sources — `invite` and `stop_link`, the addresses that carry
marketing consent and the mandatory one-tap stop — took four edits in four files:

    ci/gen_templates.py                     builds the library from the specification
    ci/check_template_fills.py              checks the built library
    ci/check_every_blank_says_who_fills_it.py   checks the specification itself
    services/operations/app/core/templates.py   validates at write time, in the service

Three were missed. The generator wrote sixty-six templates carrying the new sources, and the other
three refused every one of them — sixty-six red lines from checks that were each correct about a
list nobody had told them about.

THAT WAS THE LUCKY DIRECTION. The dangerous one is the same drift with the failure inverted: a
source added to the SERVICE and not to the checks passes review, reaches the library, and is
resolved by no renderer — so the blank falls through to «system» and the customer receives the
library's positional meaning where the shop's discount should have been. That exact defect has
already happened once here (ح-1), which is why every reader branches on these names.

THE RULE, WITH NO EXCEPTIONS TABLE. All four tuples hold the same names. Order is not compared —
these are sets of permitted values, and a reordering changes nothing about what is accepted.

WHAT IT CANNOT SEE, said plainly:
  · a fifth file with its own list. The four are named below and the search is by path, never by a
    list of allowed offenders — a new one is a line here, added by whoever writes it;
  · whether a name in the list is actually RESOLVED by the renderer. A source every file permits
    and nothing fills is a different defect, and `check_template_fills.py` is where it belongs.

    python ci/check_who_fills_a_blank_is_one_vocabulary.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: path -> the module-level name holding the vocabulary. Two of them call it `FILLS` and one calls
#: it `KINDS`; the name is not the point, the contents are.
SOURCES = {
    "ci/gen_templates.py": "FILLS",
    "ci/check_template_fills.py": "FILLS",
    "ci/check_every_blank_says_who_fills_it.py": "KINDS",
    "services/operations/app/core/templates.py": "FILLS",
}


def _tuple(path: pathlib.Path, name: str) -> tuple[str, ...] | None:
    """The value of a module-level `name = (...)`, read from the SOURCE.

    Not imported: one of these lives inside a service with its own dependency set, and a gate that
    needs the product installed is a gate that stops running.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    value = ast.literal_eval(node.value)
                except ValueError:
                    return None
                if isinstance(value, (tuple, list, set, frozenset)):
                    return tuple(str(v) for v in value)
    return None


def main() -> int:
    found: dict[str, tuple[str, ...]] = {}
    for rel, name in SOURCES.items():
        path = ROOT / rel
        if not path.is_file():
            # SILENCE IS NOT AGREEMENT. A missing file makes the comparison vacuous, and a gate that
            # passes for having found nothing is the failure it exists to prevent.
            print(f"FAIL: {rel} is missing — this gate compared three lists instead of four, "
                  f"which is not the same as four lists agreeing")
            return 1
        values = _tuple(path, name)
        if values is None:
            print(f"FAIL: no module-level `{name} = (...)` literal in {rel} — either the "
                  f"vocabulary moved, or it stopped being something this gate can read")
            return 1
        found[rel] = values

    reference_path, reference = next(iter(found.items()))
    wrong = {rel: v for rel, v in found.items() if set(v) != set(reference)}
    if wrong:
        print("FAIL: the four files disagree about who may fill a template blank")
        print(f"  {reference_path}: {sorted(set(reference))}")
        for rel, values in wrong.items():
            missing = sorted(set(reference) - set(values))
            extra = sorted(set(values) - set(reference))
            print(f"  {rel}: missing {missing or '—'}, extra {extra or '—'}")
        print("\n  A source one file permits and another refuses is a template that passes review "
              "and is filled by nothing — the blank falls through to «system» and the customer "
              "reads the library's positional meaning instead of the shop's own value (ح-1).")
        return 1

    print(f"OK: 4 files, one vocabulary of {len(set(reference))} fill sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
