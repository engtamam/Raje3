"""No two tab strips render stacked in one view — never 2, whether primary or nested.

THE OWNER'S OWN RULE, WORD FOR WORD: "ممنوع اطلاقاً يطلع شريطين تحت بعض" — a screen must never
show two tab-switcher strips (rj-ui's `Segmented` or `TabBar`) directly on top of each other,
whatever their level. It does not matter which one is "the main tab" and which is "the sub tab" —
stacking two of them reads as "a ruler under a ruler" (his own words: «صاير كنها مسطرة تحتها
مسطرة»), not as a page and a choice inside it. `AccountPanes`'s own «الفروع والفريق» tab renders
`Team.tsx`, which renders its own `people`/`branches` switcher directly below — two strips, no
screen between them, found from a live screenshot.

WHAT THIS CATCHES, TWO SHAPES OF THE SAME DEFECT:

  same-file — a single screen renders two (or more) tab-strip elements in its own JSX. The
  clearest case IS two switchers a person can see at once; a screen that legitimately shows only
  one of several strips at a time (a true `if (tab === 'x')` branch per strip) is a false
  positive this gate accepts, on purpose — a gate that must parse which JSX branches are mutually
  exclusive is a gate nobody can read in one sitting, and every case it flags gets a human look in
  the redesign pass this gate exists to seed, not a compiler-grade proof.

  parent-renders-child — a screen renders its own tab strip AND renders a local, same-repo
  component that (independently) renders its own tab strip. `Team.tsx` never renders a `Segmented`
  next to `AccountPanes`'s JSX textually — the stack only exists once the browser puts one
  component's page inside the other's tab body. Catching THIS shape is why the gate walks the
  render graph instead of stopping at "does this one file mention two switchers."

WHAT IT DOES NOT DO: distinguish a navigation tab (page section switch) from a content filter
(state/class toggle) — both `Segmented` and `TabBar` count, on the same "sit down and analyse all
of them" instruction this gate exists to satisfy. Trimming false positives is the next session's
job, once every real instance is on one list instead of found one screenshot at a time.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"

STRIP_TAG = re.compile(r"<(Segmented|TabBar)\b")
IMPORT_LOCAL = re.compile(
    r"import\s*\{([^}]*)\}\s*from\s*['\"](\.[^'\"]*)['\"]"
)
JSX_TAG = re.compile(r"<([A-Z][A-Za-z0-9]*)\b")


def resolve(base: pathlib.Path, rel: str) -> pathlib.Path | None:
    """A relative import's specifier to the actual .tsx/.ts file it names, or None if the
    file isn't part of this scan (e.g. it points outside apps/console/src, or doesn't exist)."""
    target = (base.parent / rel).resolve()
    for candidate in (target, target.with_suffix(".tsx"), target.with_suffix(".ts"),
                      target / "index.tsx", target / "index.ts"):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    if not CONSOLE.is_dir():
        print("no apps/console/src — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(f for f in CONSOLE.rglob("*.tsx") if not f.name.endswith(".test.tsx"))
    if not files:
        # SILENCE IS NOT AGREEMENT.
        print("no console screen sources found — this gate needs re-pointing")
        return 1

    strip_counts: dict[pathlib.Path, int] = {}
    local_renders: dict[pathlib.Path, dict[str, pathlib.Path]] = {}

    for f in files:
        text = f.read_text(encoding="utf-8")
        strip_counts[f] = len(STRIP_TAG.findall(text))

        # WHICH LOCAL NAMES THIS FILE IMPORTS, AND WHERE FROM — only relative imports count;
        # a name imported from an npm package is never a screen with its own tab strip.
        name_to_file: dict[str, pathlib.Path] = {}
        for names, rel in IMPORT_LOCAL.findall(text):
            resolved = resolve(f, rel)
            if resolved is None:
                continue
            for raw in names.split(","):
                name = raw.strip().split(" as ")[-1].strip()
                if name:
                    name_to_file[name] = resolved

        # ONLY NAMES THIS FILE ACTUALLY RENDERS IN JSX, not every name it happens to import —
        # a screen that imports a type or a helper alongside a component must not be linked to
        # that component's own file just because both came from the same import statement.
        rendered = {tag for tag in JSX_TAG.findall(text) if tag in name_to_file}
        local_renders[f] = {tag: name_to_file[tag] for tag in rendered}

    violations: list[str] = []

    for f in files:
        if strip_counts.get(f, 0) >= 2:
            violations.append(
                f"{f.relative_to(ROOT)} — renders {strip_counts[f]} tab strips itself "
                f"(Segmented/TabBar) — review whether they can ever both be on screen"
            )

    for f, children in local_renders.items():
        if strip_counts.get(f, 0) == 0:
            continue
        for name, child_file in children.items():
            if strip_counts.get(child_file, 0) > 0:
                violations.append(
                    f"{f.relative_to(ROOT)} renders its own tab strip AND renders <{name}> "
                    f"({child_file.relative_to(ROOT)}), which renders its own — a strip stacked "
                    f"under a strip"
                )

    if violations:
        print(f"  ✗ {len(violations)} stacked-tab-strip finding(s):")
        for v in sorted(set(violations)):
            print(f"      · {v}")
        return 1

    print("  ✔ no screen renders two tab strips stacked, directly or through a child component")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
