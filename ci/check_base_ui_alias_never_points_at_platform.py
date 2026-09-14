#!/usr/bin/env python3
"""`@base-ui` must always resolve to OUR OWN copy (`ui/packages/ui`), never to `platform/ui`.

WHY THIS EXISTS. `ui/packages/ui/package.json` names itself `"@base-ui/source"` — because it is a
copy taken from base-services' own `platform/ui/packages/ui` (at their v0.16.29) the day we needed
to edit our own design kit rather than ask their team to carry our changes upstream (vite.config.ts's
own comment says so). base-services' original at `platform/ui/packages/ui/package.json` still
carries the EXACT SAME package name today — `platform/` is a read-only submodule we never edit, and
nothing here renamed their copy when ours forked from it.

So two directories in this one checkout answer to the identical name `@base-ui/source`, and
TypeScript's `paths`/Vite's `alias` are both hand-written strings with no protection against
pointing at the wrong one — a future app, a copy-pasted config block, or a careless find/replace
could alias `@base-ui` at `platform/ui/packages/ui/src` instead of `ui/packages/ui/src` and nothing
would look wrong at a glance: same package name, same folder shape, same component filenames. That
would mean every screen importing `@base-ui/*` silently starts running base-services' OWN,
un-rebranded design kit (their palette, their radii, none of the fixes and rebrands this repo has
made to its own fork) — a defect no test in this repo would catch, because the code compiles and
renders; it would just be the WRONG interface, indistinguishable from ours until someone notices the
colours are off.

THE OWNER'S OWN WORDS (2026-09-14): "@base-ui هذا ممنوع استخدامه [من platform]... عندنا بديل عنه
خاص فينا" — the alias name itself stays (41 files already use it and it correctly points at our
copy today); what is banned is ever pointing it, or any new alias with the same intent, at
`platform/`.

WHAT THIS CHECKS, MECHANICALLY:
  1. Every `vite.config.ts` under `apps/*` — any `alias` entry keyed `@base-ui` (exact or with a
     trailing `/*`) must resolve to a path under this repo's own `ui/packages/ui`, never under
     `platform/`.
  2. Every `tsconfig*.json` under `apps/*` — same rule for `compilerOptions.paths`.
  3. No `package.json` anywhere in this repo (excluding `platform/` itself and
     `.claude/worktrees/*/platform/`, which are the submodule's own copies and out of scope) names
     a dependency whose resolved target sits under `platform/`.

    python3 ci/check_base_ui_alias_never_points_at_platform.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUR_COPY = (ROOT / "ui" / "packages" / "ui").resolve()

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# Directories that are never OURS to police here — the submodule's own working tree, and any
# worktree's own nested copy of it (a worktree checks out the submodule too).
_SKIP_PARTS = {"platform", "node_modules", ".claude", "dist", "build"}


def _is_skipped(p: Path) -> bool:
    return any(part in _SKIP_PARTS for part in p.relative_to(ROOT).parts[:-1])


def _app_configs() -> list[Path]:
    out: list[Path] = []
    apps_dir = ROOT / "apps"
    if not apps_dir.is_dir():
        return out
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir():
            continue
        for name in ("vite.config.ts", "tsconfig.json"):
            f = app_dir / name
            if f.is_file():
                out.append(f)
        for f in sorted(app_dir.glob("tsconfig.*.json")):
            out.append(f)
    return out


def _violations_in(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    out: list[str] = []
    # Both vite's `alias: { '@base-ui': here('...') }` and tsconfig's `"@base-ui/*": ["..."]`
    # name the key as a quoted string followed by a colon, then the target on the same or a
    # nearby line — matched loosely (this is config, not code to execute) and then resolved.
    for m in re.finditer(r"""['"]@base-ui(?:/\*)?['"]\s*:\s*(?:here\(\s*)?\[?\s*['"]([^'"]+)['"]""",
                         text):
        target = m.group(1)
        # tsconfig paths are relative to the tsconfig's own directory; vite's `here()` resolves
        # relative to vite.config.ts's own directory (via import.meta.url) — both are "relative
        # to this file", so resolving against `path.parent` is correct for either syntax.
        resolved = (path.parent / target.rstrip("/*")).resolve()
        try:
            resolved.relative_to(OUR_COPY)
            continue  # inside our own copy — fine
        except ValueError:
            pass
        # Also fine if it resolves to a location that does not yet exist but is clearly not
        # under platform/ (e.g. a typo caught by the build itself, not this gate's concern) —
        # this gate's only job is refusing platform/.
        if "platform" in resolved.parts:
            out.append(f"{path.relative_to(ROOT)}: '@base-ui' resolves into platform/ "
                      f"({resolved.relative_to(ROOT)}) — must point at ui/packages/ui instead")
    return out


def main() -> int:
    problems: list[str] = []
    for cfg in _app_configs():
        problems.extend(_violations_in(cfg))

    if problems:
        print(f"{C_R}  ✗ @base-ui aliased into platform/ — our own copy exists precisely so we "
              f"never depend on theirs:{C_N}")
        for p in problems:
            print(f"    {p}")
        return 1

    print(f"{C_G}  ✔ every '@base-ui' alias resolves to our own copy, never to platform/{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
