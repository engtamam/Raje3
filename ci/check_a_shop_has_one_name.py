"""A shop has ONE name, and no code may invent a second one (#327).

WHAT HAPPENED. `tenant.name` is captured once at signup. For a long time the registry would neither
expose it to our services nor let anybody change it, so the console wrote a second name into
`branding.display_name` and five services learned to prefer that one. A pilot shop then signed up
with a password autofilled into the name box, and the owner read a garbage account name at the top
of his own screen while his customers read a different string entirely — and the honest answer to
«why does my shop have two names?» was «because we could not fix the first one».

Platform v0.16.13 exposes `name` to peers AND accepts a rename, so the workaround is deleted rather
than kept beside its replacement. This gate is what stops it growing back: the next service that
needs a display name will find the field it reaches for is refused here, with the reason.

WHY A GATE AND NOT A COMMENT. The duplicate did not arrive by decision; it arrived because one
reader needed a name and the nearest field carried one. That is a pull, not an event — and a pull
is answered by a check, not by a note somebody may or may not read.

No exceptions table. If a shop ever genuinely needs a second, different public name, that is a
product decision with a screen and a migration behind it, and it argues its case by editing this
file.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIELD = "display_name"
LOOK_IN = (
    ROOT / "services",
    ROOT / "apps" / "console" / "src",
)
SKIP_PARTS = {".venv", "node_modules", "__pycache__", "dist", ".git", ".claude", "platform"}


def main() -> int:
    bad = []
    for root in LOOK_IN:
        for path in sorted(root.rglob("*")):
            if path.is_dir() or path.suffix not in (".py", ".ts", ".tsx", ".json"):
                continue
            if SKIP_PARTS & set(path.relative_to(ROOT).parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if FIELD not in line:
                    continue
                # A LINE THAT ONLY TALKS ABOUT IT IS NOT A LINE THAT USES IT. The commit that
                # removed the second name explains itself where it stood, and a check that forbade
                # the explanation would delete the reason along with the field.
                stripped = line.strip()
                if stripped.startswith(("#", "//", "*", "/*")):
                    continue
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{number} · {stripped[:90]}")

    if bad:
        print(f"A second shop name is being written or read (`{FIELD}`):")
        for line in bad:
            print("  " + line)
        print("\nA shop has one name: the tenant's `name`. The owner changes it through")
        print("`operations.set_shop_name`, which proxies the registry's rename.")
        return 1
    print("a shop has one name")
    return 0


if __name__ == "__main__":
    sys.exit(main())
