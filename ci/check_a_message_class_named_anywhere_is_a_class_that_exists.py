#!/usr/bin/env python3
"""A MESSAGE CLASS NAMED IN A RULE MUST BE ONE THE PRODUCT ACTUALLY SENDS.

WHAT THIS FOUND, AND IT WOULD HAVE CORRUPTED THE ONE NUMBER WE SELL ON.

The control group — the 10% of customers held back from messages so the difference between them
and everyone else is evidence rather than our opinion — decides what to withhold from a set:

    WITHHELD_CLASSES = frozenset({"marketing", "reminder"})

There is no class called `reminder`. The vocabulary is `service · personal · warning
· marketing`, declared in `reminders/app/core/models.py` and used by the gate, the templates and
every scheduler. Every reminder in the product is scheduled as `service`; so is every rung of the
follow-up ladder.

So the moment `HOLDOUT_ENABLED` is raised, MARKETING ALONE is withheld — and `insights` publishes
«أثر الرسائل، مقيساً» as the difference between two groups, one of which supposedly receives no
messages. Both groups receive every reminder, every follow-up and every ladder rung. The difference
is noise, published with confidence, in the only figure that claims not to be us talking about
ourselves — and it errs in the direction that flatters us.

`"reminder"` is what the concept is CALLED in every conversation about this product. That is
exactly why it was written, and exactly why nobody reading it noticed: it is the obvious word,
and it is not the word the system uses.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. Any string literal in a set or tuple named
`*_CLASSES` must appear in the declared vocabulary. A class the product cannot send is not a
narrower rule — it is a rule that silently does nothing, which is the shape of every defect in
this register.

WHY NOT CHECK EVERY `cls == "..."` COMPARISON. Because a comparison against an unknown value is
sometimes deliberate (a defensive branch, a legacy value being migrated), and a gate that
overreaches gets loosened. A NAMED SET of classes is a declaration of policy: it has no reason to
contain a name that means nothing.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The one place the vocabulary is declared. Read rather than duplicated: a copy here would be a
# second place the truth lives, and the day they disagree this gate becomes the liar.
VOCAB_FILE = SERVICES / "reminders" / "app" / "core" / "models.py"
VOCAB_NAME = "CLASSES"


def vocabulary() -> tuple[frozenset[str], str]:
    try:
        tree = ast.parse(VOCAB_FILE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return frozenset(), f"cannot read {VOCAB_FILE.name} — {exc}"
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == VOCAB_NAME for t in node.targets):
            continue
        if not isinstance(node.value, (ast.Tuple, ast.List, ast.Set)):
            continue
        names = {e.value for e in node.value.elts
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if names:
            return frozenset(names), ""
    return frozenset(), (
        f"{VOCAB_NAME} is not declared as a literal in {VOCAB_FILE.name} any more — the vocabulary "
        f"this gate compares against has moved, and comparing to nothing is not agreement")


def _named_class_sets(tree: ast.AST) -> list[tuple[str, int, set[str]]]:
    """`X_CLASSES = frozenset({...})` / `= {...}` / `= (...)` → (name, line, members)."""
    out: list[tuple[str, int, set[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not any(n.endswith("_CLASSES") for n in names):
            continue
        value = node.value
        # Unwrap frozenset({...}) / set([...]) — the wrapper is not the declaration.
        if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id in ("frozenset", "set", "tuple", "list") and value.args):
            value = value.args[0]
        if not isinstance(value, (ast.Set, ast.Tuple, ast.List)):
            continue
        members = {e.value for e in value.elts
                   if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if members:
            out.append((names[0], node.lineno, members))
    return out


def main() -> int:
    vocab, why_not = vocabulary()
    if not vocab:
        print(f"{C_R}the message-class vocabulary cannot be read{C_N}\n  {why_not}")
        return 1

    bad: list[str] = []
    checked = 0

    files = [p for p in sorted(SERVICES.rglob("*.py"))
             if "test" not in p.parts and not p.name.startswith("test_")]
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        for name, line, members in _named_class_sets(tree):
            checked += 1
            unknown = sorted(members - vocab)
            if unknown:
                bad.append(
                    f"{rel}:{line}: {name} names {', '.join(repr(u) for u in unknown)} — no such "
                    f"message class. The vocabulary is {', '.join(sorted(vocab))}. A rule written "
                    f"about a class nothing sends does not narrow the rule; it silently drops that "
                    f"part of it, and everything downstream keeps reporting as though it applied")

    if bad:
        print(f"{C_R}a rule names a message class the product cannot send{C_N}")
        for line in bad:
            print(f"  {line}")
        print(f"\n  The classes are declared in {VOCAB_FILE.relative_to(ROOT).as_posix()}.")
        return 1

    if checked == 0:
        print(f"{C_R}no *_CLASSES sets found — either they were renamed or this gate no longer "
              f"matches them, and an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {checked} class sets, every name in them a class that exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
