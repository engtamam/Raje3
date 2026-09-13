"""A line that merely INVITES must never stop a message that is lawful without it.

WHAT THE MEASUREMENT ACTUALLY SHOWED, AND IT WAS NOT WHAT ANYBODY BELIEVED.

The fleet could send nothing, and both of us described the cause as «the mandatory stop link points
at a portal that is switched off». It does not. Counted from the shipped library:

    stop_link   30 wordings — every one of them MARKETING
    invite      36 wordings — service, personal, warning

No service wording has ever carried a stop link. The thirty-six that fail to render are the
MARKETING OPT-IN INVITATION riding in the last line of a utility text — and it needs an address
only for somebody who has never been asked, because that is the screen where he would say yes.

THE TWO ARE NOT THE SAME KIND OF LINE, AND THE CODE TREATED THEM AS ONE:

  · `stop_link` is the customer's one-tap exit from marketing. It is required, and a promotional
    message without it must not go — refusing to render is exactly right.
  · `invite` is an offer to opt in. Nothing legal turns on it. A visit confirmation that cannot
    carry an invitation is still a perfectly lawful visit confirmation — and killing it means the
    shop's whole service traffic stops so that an invitation nobody is waiting for can be perfect.

THE RULE. A fill that is legally mandatory may refuse a message. Every other link-bearing line must
degrade to a sentence that promises nothing it cannot deliver. `MANDATORY` below is the whole list,
and it is short on purpose: adding to it is adding a way for the product to fall silent.

    python ci/check_only_a_mandatory_line_may_stop_a_message.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

#: THE ONLY LINE WHOSE ABSENCE MAY STOP A MESSAGE. WhatsApp's own rules and §8.3: a promotional
#: message must carry a one-tap way out. Everything else is ours to soften.
MANDATORY = {"stop_link"}

#: Where each optional link-bearing line is composed. A module here must be able to answer without
#: an address — which means catching the refusal `links.py` raises and returning prose instead.
OPTIONAL_LINE_MODULES = {"invite": pathlib.Path("app") / "core" / "invite.py"}

#: What `links.py` raises when it cannot compose an address.
REFUSAL = "LinkError"


def _handles(handler: ast.ExceptHandler) -> bool:
    node = handler.type
    if node is None:
        return False
    parts = node.elts if isinstance(node, ast.Tuple) else [node]
    for part in parts:
        if isinstance(part, ast.Attribute) and part.attr == REFUSAL:
            return True
        if isinstance(part, ast.Name) and part.id == REFUSAL:
            return True
    return False


def main() -> int:
    if not SERVICES.is_dir():
        print("services/ is missing — this gate cannot answer, and that is not a pass")
        return 1

    bad: list[str] = []
    checked = 0
    for service in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        for fill, relative in sorted(OPTIONAL_LINE_MODULES.items()):
            path = service / relative
            if not path.is_file():
                continue
            checked += 1
            tree = ast.parse(path.read_text(encoding="utf-8"))
            guarded = any(isinstance(n, ast.Try) and any(_handles(h) for h in n.handlers)
                          for n in ast.walk(tree))
            if not guarded:
                bad.append(f"{service.name}/{relative.as_posix()}: the «{fill}» line cannot "
                           f"answer without an address — it lets {REFUSAL} through, and every "
                           f"message carrying it dies with it")

    if not checked:
        # NOTHING TO CHECK IS NOT A PASS. The module moved, or the line was renamed; either way
        # this gate stopped watching and would have said nothing about it.
        print(f"  \033[31m✘ none of the optional line modules exist where this gate looks — "
              f"point it at where they went\033[0m")
        return 1

    if bad:
        print("  \033[31m✘ an invitation can silence a message that needs no invitation:\033[0m")
        for line in bad:
            print(f"      \033[31m{line}\033[0m")
        print(f"\n    Catch the refusal and return a line that promises nothing — the message is "
              f"lawful without\n    it. Only {sorted(MANDATORY)} may stop a send. Do not exempt "
              f"it here.")
        return 1

    print(f"  \033[32m✔ only a legally mandatory line can stop a message "
          f"({checked} optional line(s) checked)\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
