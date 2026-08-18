"""The class of an owner's own wording is READ from the reason, never taken from the request.

WHAT THIS CLOSES. `cls` is the field that decides everything the law and Meta's policy impose on a
message: the mandatory «أوقفها» link (§8.3), whether granted marketing consent is required, the
quiet window, and the monthly marketing cap. It arrived as a request field with a default of
`"service"` — the most permissive value — and the only screen that writes a custom template posts
no class at all. So an owner rewriting «استرجاع» in his own words had advertising filed as a
service message: no stop link, no consent check, sent at night, outside the cap.

Nothing refused it and nothing looked wrong. That is the whole reason this is a build gate.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE: any request model that carries a message class must
declare it OPTIONAL AND EMPTY BY DEFAULT — never `"service"`, never `"marketing"`, never any other
class. A default class is a decision about consent made by whoever forgot to send a field.

WHAT IT CANNOT SEE: whether the derivation picks the RIGHT reason. That is pinned by
services/reminders/tests/unit/test_a_rewritten_marketing_text_stays_marketing.py, which walks the
chain and asserts the stop link arrives.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

# The classes the product knows. Read from reminders' own registry rather than written here twice:
# a class added there and forgotten here would be a default this gate waves through.
REGISTRY = (SERVICES / "reminders" / "app" / "core" / "reasons.py").read_text(encoding="utf-8")
CLASSES = set(re.findall(r'^([A-Z]+) = "([a-z]+)"$', REGISTRY, re.M))
KNOWN = {v for _, v in CLASSES} or {"service", "marketing", "personal", "awareness", "warning"}

# A pydantic field named `cls` with a string default — the shape that decides by omission.
DEFAULTED = re.compile(r'^\s*cls:\s*str\s*=\s*Field\([^)]*default="([a-z]+)"', re.M)


def main() -> int:
    bad: list[str] = []
    checked = 0
    for path in sorted(SERVICES.rglob("app/**/*.py")):
        if "/tests/" in path.as_posix():
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        for m in DEFAULTED.finditer(src):
            checked += 1
            value = m.group(1)
            if value in KNOWN:
                line = src[:m.start()].count("\n") + 1
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{line} defaults the class to "
                           f"«{value}»")

    for b in bad:
        print(f"  \033[31m✗ {b}\033[0m")
    if bad:
        print("\nA message class decides the mandatory stop link, the consent required, the quiet "
              "window and the monthly cap. A default means a caller that omits the field decides "
              "all four by accident — read the class from the reason instead.")
        return 1
    print(f"ok no request model decides a message class by default ({checked} class fields read)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
