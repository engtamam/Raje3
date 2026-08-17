"""The i18n gate — no raw key, and no raw English, ever reaches a screen.

WHAT IT CATCHES, and it is not hypothetical: the kit's auth components read every label through
`useAuthI18n()`, a seam that OUTSIDE a provider returns the key itself. An unwrapped console does
not fall back to English — it paints `auth.otp.hint 0505536720` at a shop owner, with his own phone
number beside a dotted identifier. It renders, it is not an error, and nothing fails.

So this reads every key the kit ASKS for and every key our dictionary ANSWERS, and fails when the
first set is not covered by the second. A screen we have not wired yet is exactly when this bites:
the key is missing today and harmless, and appears on the day somebody routes to it.

AND A COMPLETE DICTIONARY IS INERT UNWRAPPED, WHICH IS THE HALF THIS GATE WAS MISSING (هـ-8). Every
key answered here reaches a screen only through a PROVIDER at the root of the console. The kit has
three seams that degrade to the raw key — auth, blockdoc, and the design system's shell — and each
is a separate wire. Remove one provider from `main.tsx` and this gate, reading only the dictionary,
went on reporting that every string has Arabic behind it while a whole family of labels rendered as
dotted identifiers. It is the same shape as د-2: the answer existed and nothing carried it.

So the seams are DISCOVERED rather than listed — a context whose default `t` returns its own key is
one by construction — and each one's provider must appear at the console's root. A fourth seam
added to the kit next release is found by the same rule, with no list to remember to extend.

AND READING NOTHING IS NOT A PASS. `platform/` is a submodule; on a checkout that has not
initialised it the glob matches no files, `asked` is empty, and this gate printed «every one of the
0 strings the kit renders has Arabic behind it» in green. That is the sentence a person trusts right
before shipping a console that paints keys at shop owners.
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
KIT = ROOT + "platform/ui/packages/ui/src/**/*.ts*"
DICT = ROOT + "apps/console/src/i18n.ts"


#: The console root, where every i18n seam must be wrapped.
ROOT_FILE = ROOT + "apps/console/src/main.tsx"

#: A context default that hands back the key it was given — the signature of a seam that degrades
#: to a raw identifier on screen rather than to English. Matching the SHAPE rather than a list of
#: names is what makes a seam added next release visible to this gate without editing it.
ECHOES_THE_KEY = re.compile(r"t:\s*\((\w+)\)\s*=>\s*\1\b")

#: The provider that carries a seam. Read out of the same file as the echoing default rather than
#: derived from a constant's name: the shell calls its default `defaultShell`, so any rule that
#: turned `XContext` into `XProvider` would miss it.
#:
#: BOTH DECLARATIONS, because the kit uses both and reading only one accused a correctly wired
#: seam. `blockdoc` and the shell write `export function XProvider(...)`; `auth/i18n.ts` writes
#: `export const AuthI18nProvider = AuthI18nContext.Provider` — a re-export of React's own, which
#: is the same wire and needs the same wrapping.
A_PROVIDER = re.compile(r"export (?:function|const) (\w*Provider)\b")


def _seams() -> list[tuple[str, str]]:
    """(file, provider) for every kit seam whose default `t` echoes the key."""
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob(KIT, recursive=True)):
        src = io.open(path, encoding="utf-8").read()
        if not ECHOES_THE_KEY.search(src):
            continue
        rel = path.replace(ROOT, "")
        providers = A_PROVIDER.findall(src)
        # A seam nobody can wrap is a fault in the kit, and it is reported rather than skipped.
        out.extend((rel, name) for name in providers) if providers else out.append((rel, ""))
    return out


def main() -> int:
    # THE WIRE, BEFORE THE WORDS. A dictionary that answers every key is worth nothing if the
    # provider carrying it is not at the root — and that failure is invisible to a check that
    # compares two sets of strings.
    seams = _seams()
    if not seams:
        print("  \033[31m✘ no i18n seam found in the kit — either platform/ is not checked out or "
              "the kit changed shape. Either way this gate checked nothing.\033[0m")
        return 1
    try:
        root_src = io.open(ROOT_FILE, encoding="utf-8").read()
    except OSError as exc:
        print(f"  \033[31m✘ cannot read the console root ({exc}) — so the providers were NOT "
              f"checked\033[0m")
        return 1
    # THE TAG, NOT THE NAME. A substring test passes on `import { AuthI18nProvider }` with no
    # element in the tree — an import is not a wire — and it also passed my own sabotage, which
    # renamed the provider to `AuthI18nProviderXx` and still contained the original. What makes a
    # seam live is an element wrapping the router, so that is what is looked for.
    unwired = [(f, p) for f, p in seams
               if not p or not re.search(r"<" + re.escape(p) + r"[\s>]", root_src)]
    if unwired:
        print("  \033[31m✘ a kit i18n seam is not wrapped at the console root — every label it "
              "carries renders as its own dotted identifier:\033[0m")
        for f, p in unwired:
            print(f"      {f}: {p or 'defines no provider at all'}")
        print("      wrap it in apps/console/src/main.tsx, outside <RouterProvider>")
        return 1

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

    if not asked:
        # SILENCE IS NOT AGREEMENT. Zero keys means the kit was not read, not that it asks for
        # nothing — and «every one of the 0 strings» printed in green is the sentence somebody
        # trusts right before shipping a console full of raw identifiers.
        print("  \033[31m✘ the kit asked for no keys at all — platform/ is not checked out, or the "
              "call shape changed. This gate checked nothing and will not say otherwise.\033[0m")
        return 1

    print(f"  \033[32m✔ every one of the {len(asked)} strings the kit renders has Arabic behind "
          f"it, and all {len(seams)} seams are wrapped at the console root\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
