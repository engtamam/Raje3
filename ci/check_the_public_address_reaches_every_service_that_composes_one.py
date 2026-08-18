"""A setting whose comment says «an install fills this» must be filled BY an install.

THE DEFECT THIS EXISTS FOR, FOUND BY READING THE CLUSTER RATHER THAN THE REPOSITORY.

`deploy/services/reminders.values.yaml` carries `PUBLIC_BASE_URL: ""` under a comment that says,
in as many words, «LEFT EMPTY UNTIL AN INSTALL FILLS IT». The installer asks for the domain once,
renders it into the edge, prints `https://<DOMAIN>/p/…` at the end of a successful run — and never
wrote it here. Nothing did. The value was empty in the repository, empty in the ConfigMap and empty
in the running pod, five days after an install that had been told the answer.

WHAT THAT COST, EXACTLY. `core/links.py` refuses to compose a link it cannot address, which is
right. So every message carrying a link failed at RENDER, before the send log and before any
screen: the campaigns engine — built, complete, sold — could not emit one, and said nothing about
why. The customer's stop screen and grant screen were live and answering 200 the whole time.

THE RULE, AND IT IS NARROW ON PURPOSE. Not «every setting must be non-empty»: a great many are
empty on purpose and mean it. Only this — a service that declares a public base and leaves it to
the installer must be filled BY the installer, selected by the declaration rather than by a list
somebody remembers to edit. One answer, every layer, the way the edge already works.

    python ci/check_the_public_address_reaches_every_service_that_composes_one.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALUES = ROOT / "deploy" / "services"
INSTALLER = ROOT / "deploy" / "bring-up.sh"

SETTING = "PUBLIC_BASE_URL"

#: The declaration: the key, present in a values file, WHATEVER its value.
#:
#: IT USED TO REQUIRE AN EMPTY ONE, and that made the repository's own value into a decision the
#: installer had to respect. Once `reminders.values.yaml` carried the real address — which it had
#: to, because a ship renders values and would otherwise wipe the ConfigMap back to blank on every
#: roll — an install for a DIFFERENT domain would have skipped it in silence, and the new cluster
#: would have composed links pointing at somebody else's site while every screen looked healthy.
#:
#: So both the installer and this now select by the KEY. Whoever declares it composes links, and
#: whoever composes links gets the domain the installer was given.
DECLARED = re.compile(rf"^\s*{SETTING}:", re.M)

#: THE SELECTION: a `grep` for the setting against the LOOP VARIABLE — each values file read in
#: turn. The filename must be `"$f"` rather than a literal, and that is the whole point: a line
#: naming `reminders` would satisfy a looser pattern and leave the next composing service silent,
#: which is this same defect wearing a different service name.
SELECTS_BY_DECLARATION = re.compile(rf'grep .*{SETTING}.*"\$f"')

#: AND «BUILT FROM DOMAIN» IS READ THROUGH THE VALUE ACTUALLY WRITTEN. Two earlier drafts of this
#: gate were weaker than the sentence they printed, and sabotage is the only reason either was
#: found:
#:
#:   1. searching the whole installer for the setting and DOMAIN in any order — `DOMAIN` appears a
#:      dozen times in a seven-hundred-line script, so hardcoding a host stayed green;
#:   2. searching a window of lines around the selection — the window reached far enough to catch
#:      an unrelated `${DOMAIN}` and stayed green for exactly the same edit.
#:
#: So it follows the value: read the shell variable the patch WRITES, then require that variable's
#: own assignment to interpolate DOMAIN. Nothing weaker counts, because nothing weaker is what
#: lands in the ConfigMap.
PATCH_WRITES = re.compile(SETTING + r'[^$]*\$([A-Za-z_][A-Za-z0-9_]*)')
DOMAIN_INTERPOLATED = re.compile(r"\$\{DOMAIN(:-)?\}")


def _assignment_of(lines: list[str], name: str) -> str:
    """The line assigning that shell variable, or "" when nothing assigns it."""
    wanted = re.compile(r"^\s*" + re.escape(name) + r"=")
    return next((line for line in lines if wanted.search(line)), "")


def main() -> int:
    if not INSTALLER.is_file():
        print(f"{INSTALLER.relative_to(ROOT)} is missing — «cannot find the installer» is not a "
              f"pass")
        return 1

    declaring = sorted(p.name for p in VALUES.glob("*.values.yaml")
                       if DECLARED.search(p.read_text(encoding="utf-8")))
    if not declaring:
        # NOBODY DECLARES IT ANY MORE. Either the setting was renamed or it is filled in place;
        # either way this gate now checks nothing, and silence would hide that.
        print(f"  \033[31m✘ no values file declares an empty «{SETTING}» — point this gate at what "
              f"replaced it\033[0m")
        return 1

    lines = INSTALLER.read_text(encoding="utf-8").splitlines()

    # THE PATCH PAYLOAD, NOT ANY MENTION. Comments in this installer discuss the setting at
    # length; only the `-p '{"data":…}'` argument is what lands in the ConfigMap. It sits on its
    # own continuation line, so this looks for the payload rather than for `patch cm` — which is
    # on the line above it and would have found nothing.
    payload = [line for line in lines
               if SETTING in line and re.search(r"-p\s+[\"']", line)]
    written = PATCH_WRITES.search(payload[0]) if payload else None

    by_declaration = any(SELECTS_BY_DECLARATION.search(line) for line in lines)
    from_domain = bool(written) and bool(
        DOMAIN_INTERPOLATED.search(_assignment_of(lines, written.group(1))))

    if not (by_declaration and from_domain):
        print(f"  \033[31m✘ {len(declaring)} service(s) leave «{SETTING}» to the installer, and the "
              f"installer does not fill it:\033[0m")
        for name in declaring:
            print(f"      \033[31m{name}\033[0m")
        if not from_domain:
            print(f"\n    bring-up.sh does not build the value it writes out of DOMAIN — the one "
                  "answer it already\n    took, and the one the edge is already rendered from.")
        if not by_declaration:
            print("\n    bring-up.sh does not select services by the declaration. Naming them "
                  "makes the next\n    composing service silent by omission.")
        print("\n    A comment promising that an install fills this is not an install filling it. "
              "Every message\n    carrying a link then dies at render, before the send log and "
              "before any screen. Do not\n    exempt it here.")
        return 1

    print(f"  \033[32m✔ the installer fills {SETTING} from DOMAIN for every service that declares "
          f"it ({len(declaring)})\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
