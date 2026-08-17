"""Every rail row carries an icon, and the shell is given it.

WHAT HAPPENED. The shell's nav item has taken an `icon` since v0.16.x and we passed `to` and
`label` only. The collapsed rail draws icons and nothing else — and the shell PERSISTS the collapse
per browser — so an owner who folded the rail once was left with seven blank rows: correctly sized,
clickable, and completely mute. He had lost his navigation, with nothing on the screen to say what
had happened or how to get it back.

Nothing failed. No error, no warning, no missing route: a nav that renders perfectly and says
nothing.

TWO HALVES, AND EITHER ONE ALONE IS THE DEFECT. A section may declare an icon that App.tsx then
drops on the way to the shell; and App.tsx may forward `icon` for sections that do not declare one.
So this checks BOTH: every entry in SECTIONS names an icon, and the `navItems` mapping passes it.

NO EXCEPTIONS TABLE. A row that genuinely has no icon has no face when collapsed, and «this one
section is a blank square» is not a design somebody chose — it is this defect with a note attached.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
NAV = ROOT / "apps" / "console" / "src" / "nav.ts"
APP = ROOT / "apps" / "console" / "src" / "App.tsx"
# A section literal: `{ ... id: 'today', ... }` on one line, which is how they are written.
ROW = re.compile(r"^\s*\{\s*(?=[^}]*\bid:\s*')(?P<body>[^}]*)\}", re.M)
ID = re.compile(r"\bid:\s*'(?P<id>[^']+)'")


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
        raise SystemExit(1) from exc


def main() -> int:
    for path in (NAV, APP):
        if not path.exists():
            print(f"cannot find {path.relative_to(ROOT).as_posix()} — this gate needs re-pointing")
            return 1

    nav = _read(NAV)
    start = nav.find("export const SECTIONS")
    if start < 0:
        # SILENCE IS NOT AGREEMENT: the list was renamed, not emptied of defects.
        print("SECTIONS not found in nav.ts — this gate needs re-pointing")
        return 1
    end = nav.find("\n];", start)
    body = nav[start:end if end > 0 else len(nav)]

    rows = [(m.group("body"), ID.search(m.group("body"))) for m in ROW.finditer(body)]
    named = [(b, i.group("id")) for b, i in rows if i]
    if not named:
        print("no sections parsed out of SECTIONS — this gate needs re-pointing")
        return 1

    faceless = [sid for b, sid in named if "icon:" not in b]

    app = _read(APP)
    forwarded = "icon: s.icon" in app or "icon: section.icon" in app

    if faceless or not forwarded:
        print("A collapsed rail would draw a blank row:")
        for sid in faceless:
            print(f"  nav.ts · section '{sid}' declares no icon")
        if not forwarded:
            print("  App.tsx · navItems does not pass `icon` to the shell, so declaring one "
                  "changes nothing")
        print("\nThe rail collapses, the choice is remembered per browser, and an icon is the "
              "only thing a folded row can say.")
        return 1
    print(f"{len(named)} nav row(s) have a face when the rail is collapsed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
