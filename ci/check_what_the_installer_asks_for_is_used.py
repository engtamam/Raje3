"""A question the installer asks must have an answer somebody reads.

WHAT THIS FOUND. `install.sh` asks the operator for an administration account — an email and a
password — enforces a twelve-character floor on the password, generates one when the field is left
blank, exports both, and prints the password under «تُعرض مرة واحدة فقط». Nothing downstream reads
either. Not `bring-up.sh`, not `mint-our-secrets.sh`, not a seed script. No account is created.

So the operator writes down a password for an account that does not exist, closes the terminal —
which is the one moment the value was ever visible — and finds out on the day they first try to
sign in. The prompt was not a stub anybody would notice: it validates, it generates, it warns you
to save the value. Every signal it gives says the value matters.

THE SHAPE, AND WHY IT IS WORTH A GATE. A prompt is a promise: it says *this answer changes what you
get*. An unread answer breaks that promise at the worst possible moment — after the install reports
success, at the boundary where the operator can no longer go back and look. And it is invisible in
review, because the asking code and the consuming code are in different files and the missing one
is missing.

THE RULE, WITH NO EXCEPTIONS TABLE. Every name `install.sh` exports must be read by something that
runs after it. `install.sh` reading its own export back does not count — the whole defect is a
value that never leaves the file that asked for it.

WHAT IT CANNOT SEE, said plainly:
  · a value read only by a script this gate does not know to look in. The search set is named in
    CONSUMERS below and is scoped by path, never by a list of allowed offenders;
  · a value that IS read but ignored — passed to a function that drops it. That is a different
    defect and needs a different check;
  · a prompt whose answer is never exported at all. Those are local to the installer and are its
    own business.

    python ci/check_what_the_installer_asks_for_is_used.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "deploy" / "install.sh"

# WHERE THE INSTALLER HANDS OFF. Everything else is reached by following invocations from here,
# because a file that mentions a value is not the same as a file that runs.
ENTRY = ROOT / "deploy" / "bring-up.sh"

# Values may also land in a chart's values file rather than in a script. Those are applied by the
# deploy path wholesale, so presence there IS consumption.
STATIC_CONSUMERS = ("deploy/services/*.values.yaml", "deploy/edge/edge.json")

# `bash "$HERE/seed/seed-x.sh"` — how one deploy script invokes another.
INVOKES = re.compile(r"""(?:bash|sh|source|\.)\s+["']?\$(?:\{)?HERE(?:\})?/([\w./-]+\.sh)""")

EXPORT = re.compile(r"^\s*export\s+(?P<names>[A-Z_][A-Z0-9_ ]*)\s*$", re.M)


def main() -> int:
    if not INSTALLER.is_file():
        print(f"FAIL: {INSTALLER.name} is missing — this gate checked nothing, and an absent "
              f"installer is not agreement")
        return 1

    src = INSTALLER.read_text(encoding="utf-8")
    exported: list[str] = []
    for m in EXPORT.finditer(src):
        exported.extend(m.group("names").split())

    # SILENCE IS NOT AGREEMENT. An installer that exports nothing would pass every check below by
    # having nothing to check — which is indistinguishable from one whose exports we failed to read.
    if not exported:
        print("FAIL: no `export` line found in install.sh — either the installer stopped handing "
              "its answers on, or this gate stopped recognising how it does. Both are the defect.")
        return 1

    # REACHED, NOT MERELY PRESENT. The first version of this gate globbed `deploy/**/*.sh` and asked
    # whether any file MENTIONED the value. It passed the moment a seeder existed — even with the
    # line that invokes it deleted, which is the exact defect one layer along: a script nothing
    # calls is as unread as no script at all. Its own sabotage did not fail it, and a check that
    # survives its sabotage is measuring something other than what it claims.
    #
    # So the set is built by FOLLOWING invocations from bring-up.sh. A file earns its place by
    # being run, not by sitting in the right folder.
    haystack: list[tuple[str, str]] = []
    seen: set[pathlib.Path] = set()
    queue = [ENTRY]
    while queue:
        path = queue.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        haystack.append((path.relative_to(ROOT).as_posix(), text))
        for rel in INVOKES.findall(text):
            queue.append((path.parent / rel).resolve())

    if ENTRY not in seen:
        print(f"FAIL: {ENTRY.name} is missing — nothing runs after the installer, so every answer "
              f"would look unread and this gate would be lying in the other direction")
        return 1

    for pattern in STATIC_CONSUMERS:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file():
                try:
                    haystack.append((path.relative_to(ROOT).as_posix(),
                                     path.read_text(encoding="utf-8", errors="ignore")))
                except OSError:
                    continue

    unread: list[str] = []
    for name in sorted(set(exported)):
        # `$NAME` or `${NAME...}` — the two ways a shell script reads it, and `NAME:` for a values
        # file that carries it as a key.
        wanted = re.compile(rf"\$\{{{name}\b|\${name}\b|^\s*{name}:", re.M)
        if not any(wanted.search(text) for _, text in haystack):
            unread.append(name)

    if unread:
        print(f"FAIL: {len(unread)} value(s) the installer asks for and nothing reads:")
        for name in unread:
            print(f"  {name} — install.sh exports it; no script or values file that runs "
                  f"afterwards mentions it")
        print("\n  A prompt is a promise that the answer changes something. Wire it, or stop "
              "asking — an unread answer is discovered by an operator, after the terminal closed.")
        return 1

    print(f"OK: {len(set(exported))} installer answer(s), every one read by something downstream")
    return 0


if __name__ == "__main__":
    sys.exit(main())
