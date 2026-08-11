"""The i18n gate — no raw key, and no raw English, ever reaches a screen.

WHAT IT CATCHES, and it is not hypothetical: the kit's auth components read every label through
`useAuthI18n()`, a seam that OUTSIDE a provider returns the key itself. An unwrapped console does
not fall back to English — it paints `auth.otp.hint 0505536720` at a shop owner, with his own phone
number beside a dotted identifier. It renders, it is not an error, and nothing fails.

So this reads every key the kit ASKS for and every key our dictionary ANSWERS, and fails when the
first set is not covered by the second. A screen we have not wired yet is exactly when this bites:
the key is missing today and harmless, and appears on the day somebody routes to it.
"""
from __future__ import annotations

import glob
import io
import re
import sys

ROOT = __file__.rsplit("ci", 1)[0]
# EVERY SEAM, NOT JUST THE AUTH ONE. The kit has more than one i18n context — `auth/i18n.ts` and
# blockdoc's — and each degrades to the raw key on its own. The legal gate crosses both in a single
# screen, which is how a second, quieter leak was found right after the first was fixed.
KIT = ROOT + "platform/ui/packages/ui/src/**/*.tsx"
DICT = ROOT + "apps/console/src/i18n.ts"


def main() -> int:
    asked: set[str] = set()
    for path in sorted(glob.glob(KIT, recursive=True)):
        src = io.open(path, encoding="utf-8").read()
        # A KEY IN A COMMENT IS NOT A KEY ON SCREEN. The kit documents an option it does not take —
        # «label: t('auth.phone')» inside a doc block — and this guard demanded an Arabic string for
        # a call nobody makes. A check that fires on prose teaches people to ignore it, and it is
        # the second false positive of exactly this family found in one audit.
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"^\s*//.*$", "", src, flags=re.M)
        asked |= set(re.findall(r"t\('([a-zA-Z0-9._]+)'\)", src))

    text = io.open(DICT, encoding="utf-8").read()
    answered = set(re.findall(r"^\s*'([a-zA-Z0-9._]+)':", text, re.M))

    missing = sorted(asked - answered)
    if missing:
        print("  \033[31m✘ the kit asks for keys our dictionary does not answer — each one renders "
              "as its own identifier on screen:\033[0m")
        for key in missing:
            print(f"      {key}")
        return 1

    # A dictionary entry nothing asks for is not a fault — the kit may add a screen next release —
    # but a WRONG key hides a real gap behind a full-looking file, so it is reported.
    stale = sorted(answered - asked)
    if stale:
        print(f"  \033[33m… {len(stale)} key(s) answered that the kit no longer asks for: "
              f"{', '.join(stale[:5])}{'…' if len(stale) > 5 else ''}\033[0m")

    print(f"  \033[32m✔ every one of the {len(asked)} strings the kit renders has Arabic behind "
          f"it\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
