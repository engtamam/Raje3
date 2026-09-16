"""Every card-shaped surface should render through <Card>, not a hand-rolled className copy.

WHY THIS EXISTS. The app-store/premium redesign (2026-09-16) replaces the shared <Card> primitive
(ui/packages/ui/src/design-system/Card.tsx) with a new, glossier one — and the whole point of that
work is that changing ONE component reaches every screen that uses it, the same reasoning that
already governs theme.config.ts. That promise is worthless if half the product's "cards" are really
a raw `<div className="rounded-card border border-border-subtle bg-surface-1 ...">` copied by hand
at the point of use: a future edit to <Card> would never reach them, and they would sit there
looking exactly like a card, subtly falling further behind the real one every redesign after this.

THIS IS THE SWEEP LIST, NOT (YET) A HARD GATE. It is wired into guards.yml and DOES fail today,
listing every hand-rolled card found — that is deliberate: the fix is "migrate this JSX site to
<Card>", a real one-at-a-time edit across many files, not something to leave silently green while
the redesign proceeds around it. Once every finding below is migrated, this clears and STAYS
clear — a future hand-rolled card is exactly the regression this exists to catch.

WHAT COUNTS. A `<div` (or `<section`/`<article`, the other two container tags a "card" is ever
drawn on) whose className carries the same signature shape <Card> renders: a `bg-surface-1` (or
`bg-white`, the same colour before the palette had a name) fill together with a `rounded-*` corner
AND a `border`/`shadow` — the combination that reads as "this is a card" to a person. A single one
of those utilities alone (e.g. a plain `rounded-full` avatar, or a `border-b` divider) is not
enough to match.

TAG, NOT JUST CLASSNAME — FOUND BY HAND AFTER THE FIRST VERSION SHIPPED. React attributes routinely
sit on their own line, so a purely className-scanning check does not know WHICH element a matching
className belongs to — the first version of this gate flagged nine sites in Visit.tsx alone that
were `<input>`/`<button>` elements sharing the exact same "raised surface" utility trio a card
uses, none of them a card in any sense a person would recognise. This version walks BACKWARD from
the className line to the nearest tag opening and only counts a `<div`/`<section`/`<article`.

THE SWEEP FINISHED (2026-09-16) — 96 real sites migrated to <Card>. What is left is ALLOWLIST, not
a backlog: every remaining match is a real, reviewed exception, never simply un-migrated. Six
shapes, each one checked by hand:
  - A floating popover/menu/dialog (`absolute`/`fixed`, role=listbox|dialog) — FilterMenu, both
    Modal components, blockdoc's own insert-palette, DocBlockRenderer's own insert-menu. <Card> has
    no positioning/backdrop story; these are a different primitive wearing a similar fill by
    coincidence, not an un-migrated card.
  - The WhatsApp preview mockup (WhatsAppPreview.tsx) — must stay pixel-true to WhatsApp's OWN
    colours (`#DCF8C6` etc.), never our theme.
  - A frosted-glass overlay row (NotificationBell.tsx) — `bg-white/[0.03]` on a dark panel is a
    deliberate one-off treatment, not a stale copy of the light palette.
  - A `ref`-driven contentEditable box (TextEditor.tsx) — `<Card>` does not forward refs; converting
    it would silently break direct DOM manipulation the editor depends on.
  - The Segmented control's own track (Segmented.tsx) — a control's chrome, not a content card.
  - One "actively being edited" ring state (blockdoc.tsx:848) — a distinct interaction state, not a
    plain card look.
ALLOWLIST is deliberately (file, line-content substring) rather than (file, line NUMBER) — a
substring survives the file being edited above the match; a bare line number silently stops
checking the right line the moment anything shifts.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCAN_DIRS = [ROOT / "apps", ROOT / "ui"]
EXCLUDE_PARTS = {"node_modules", "dist", "build", ".git", "coverage", "e2e"}
CARD_COMPONENT_FILE = ROOT / "ui" / "packages" / "ui" / "src" / "design-system" / "Card.tsx"
RJ_CARD_COMPONENT_FILE = ROOT / "apps" / "console" / "src" / "rj-ui" / "Card.tsx"

FILL_RE = re.compile(r"\bbg-(?:surface-1|white)\b")
RADIUS_RE = re.compile(r"\brounded-(?:card|lg|xl|2xl|\[[^\]]+\])\b")
EDGE_RE = re.compile(r"\b(?:border(?:-\S+)?|shadow-(?:sm|md|lg|pop))\b")

# A line that opens an element already using the shared component — never a finding, however its
# OWN className happens to look (it may legitimately restyle within <Card className="...">).
CARD_USAGE_RE = re.compile(r"<Card\b")

TAG_OPEN_RE = re.compile(r"<([A-Za-z][\w.]*)\b")
CONTAINER_TAGS = {"div", "section", "article"}
# Non-container tags that legitimately carry the exact same "raised surface" utility trio without
# being a card — found live in Visit.tsx, all nine of its first-version findings.
NON_CONTAINER_TAGS = {"input", "button", "textarea", "select", "a", "img", "span", "li", "ul",
                      "ol", "p", "h1", "h2", "h3", "h4", "h5", "h6", "svg", "label", "form"}

# (relative path, substring of the flagged line) — see this module's own docstring for why each
# one is a reviewed exception, not an un-migrated card. A finding is suppressed only when BOTH the
# path and the substring match, so this stays specific to the one line it was written for.
ALLOWLIST: set[tuple[str, str]] = {
    ("apps/console/src/NotificationBell.tsx", "bg-white/[0.03]"),
    ("apps/console/src/rj-ui/FilterMenu.tsx", "absolute top-full"),
    ("apps/console/src/rj-ui/Modal.tsx", "rounded-card border border-border-subtle bg-surface-1 shadow-pop"),
    ("apps/console/src/rj-ui/WhatsAppPreview.tsx", "bg-[#DCF8C6]"),
    ("apps/console/src/rj-ui/WhatsAppPreview.tsx", "border-black/10 bg-white"),
    ("apps/console/src/rj-ui/WhatsAppPreview.tsx", "flex w-[280px] flex-col overflow-hidden rounded-lg bg-white"),
    ("apps/console/src/rj-ui/WhatsAppPreview.tsx", "border-danger-soft bg-white"),
    ("apps/console/src/screens/TextEditor.tsx", "focus:border-accent"),
    ("ui/packages/ui/src/components/blockdoc.tsx", "border-accent/40 bg-surface-1 px-2 py-1"),
    ("ui/packages/ui/src/components/blockdoc.tsx", "ring-1 ring-accent/10"),
    ("ui/packages/ui/src/components/DocBlockRenderer.tsx", "absolute top-6 z-20"),
    ("ui/packages/ui/src/design-system/Modal.tsx", "rounded-card border border-border-subtle bg-surface-1 shadow-pop"),
    ("ui/packages/ui/src/design-system/Segmented.tsx", "inline-flex flex-wrap gap-1"),
}


def _files():
    for base in SCAN_DIRS:
        for path in base.rglob("*.tsx"):
            if any(part in EXCLUDE_PARTS for part in path.parts):
                continue
            if path in (CARD_COMPONENT_FILE, RJ_CARD_COMPONENT_FILE):
                continue
            yield path


def _owning_tag(lines: list[str], lineno_idx: int) -> str | None:
    """Walk backward from `lineno_idx` (0-based) to the nearest `<TagName` opening — attributes,
    including className, routinely sit on their own line below it."""
    for i in range(lineno_idx, max(-1, lineno_idx - 40), -1):
        m = TAG_OPEN_RE.search(lines[i])
        if m:
            return m.group(1).lower()
    return None


def main() -> int:
    findings: list[str] = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            lineno = idx + 1
            if CARD_USAGE_RE.search(line):
                continue
            if not (FILL_RE.search(line) and RADIUS_RE.search(line) and EDGE_RE.search(line)):
                continue
            tag = _owning_tag(lines, idx)
            if tag is None or tag in NON_CONTAINER_TAGS or tag not in CONTAINER_TAGS:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if any(rel == p and sub in line for p, sub in ALLOWLIST):
                continue
            findings.append(f"{rel}:{lineno}")

    if findings:
        print(f"{len(findings)} hand-rolled card(s) found — migrate each to <Card> from "
              f"ui/packages/ui/src/design-system/Card.tsx:")
        for line in findings:
            print("  " + line)
        return 1

    print("no hand-rolled cards found across apps/ and ui/ — every card-shaped surface uses <Card>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
