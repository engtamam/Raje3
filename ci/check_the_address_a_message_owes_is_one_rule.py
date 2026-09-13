"""Which address a message must end with is decided in one place, for our texts and for his.

THE RULE ITSELF. Every message ends with the one address it owes its reader: marketing owes a
one-tap stop (§8.3, a legal requirement rather than a courtesy), everything else owes the
invitation — the only door marketing consent can ever come through. A utility message without it
is a dead end, and a shop whose every message is a dead end can never lawfully run a campaign.

WHY THIS NEEDS A STANDING CHECK RATHER THAN CARE. The rule has THREE readers, and they were built
months apart for different audiences:

  · `ci/gen_templates.py` enforces it over OUR library of 66 texts, at build time;
  · `services/reminders/app/core/custom_templates.py` appends it to the owner's own draft and
    refuses a body that lost it, at runtime;
  · `services/reminders/app/core/reasons.py` names it once so the other two can ask.

This is the shape that has already cost this codebase a full day: the vocabulary of who may fill a
blank lived in FOUR files, one was updated, and the other three rejected all 66 templates. Nothing
about a rule spread across readers announces that it has drifted — the drift IS the silence.

WHAT DRIFT WOULD LOOK LIKE IN PRODUCTION, and why neither half is noticeable on its own: if the
generator and the runtime disagreed about `marketing`, our own library would carry a stop link and
a shop's own promotional text would carry an invitation instead. Both submit. Both get approved.
The shop's marketing then goes out with no way to stop it, under its own name, against its own
licence — and the first evidence is a complaint.

WHAT THIS CANNOT SEE, said plainly: whether the rule is RIGHT. If both readers agree that marketing
owes an invitation, this passes and the product is unlawful. That is a question for §8.3 and a
human, and no equality check can stand in for it.

    python ci/check_the_address_a_message_owes_is_one_rule.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Every class a message can have. Not read from either side — written here on purpose, so that a
#: class DELETED from one reader is a failure rather than a silently smaller agreement.
CLASSES = ("service", "personal", "warning", "marketing")


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    reasons_path = ROOT / "services/reminders/app/core/reasons.py"
    generator_path = ROOT / "ci/gen_templates.py"
    for path in (reasons_path, generator_path):
        if not path.is_file():
            # SILENCE IS NOT AGREEMENT. A reader that moved makes this check vacuous, and a gate
            # that passes for having read nothing is the failure it exists to prevent.
            print(f"FAIL: {path.relative_to(ROOT)} is missing — this gate read nothing, which is "
                  f"not the same as finding nothing")
            return 1

    sys.path.insert(0, str(ROOT / "services/reminders"))
    try:
        reasons = _load(reasons_path, "_reasons_under_check")
        generator = _load(generator_path, "_generator_under_check")
    except Exception as exc:                                    # noqa: BLE001
        print(f"FAIL: could not read both sides of the rule — {exc}")
        return 1

    runtime = getattr(reasons, "mandatory_tail", None)
    if runtime is None:
        print("FAIL: reasons.mandatory_tail is gone — the rule has no single owner any more, and "
              "whatever replaced it is not what the generator and the draft path are asking")
        return 1
    table = getattr(generator, "LAST_FILL", None)
    default = getattr(generator, "LAST_FILL_DEFAULT", None)
    if table is None or default is None:
        print("FAIL: gen_templates no longer declares LAST_FILL / LAST_FILL_DEFAULT — our own "
              "library is then unchecked, whatever the runtime does about his")
        return 1

    problems = []
    for cls in CLASSES:
        theirs = table.get(cls, default)
        ours = runtime(cls)
        if theirs != ours:
            problems.append(
                f"  «{cls}»: the library generator ends it with «{theirs}», the runtime with "
                f"«{ours}»")

    if problems:
        print(f"FAIL: the two readers of one rule disagree about {len(problems)} class(es):")
        for p in problems:
            print(p)
        print("\n  `reasons.mandatory_tail` is the sentence; `gen_templates.LAST_FILL` must be a "
              "restatement of it and nothing else. Marketing owes a one-tap stop (§8.3); every "
              "other class owes the invitation that is the only way consent can be given.")
        return 1

    print(f"OK: {len(CLASSES)} message classes, and both readers of the rule give one answer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
