"""A name that stops being a tab must still lead somewhere, and no tab may be unreachable.

WHY THIS EXISTS. «حسابي» is four tabs, and half the product links INTO them: every locked card in
the console says «أضِفه إلى اشتراكي» and opens `?tab=…`, the messages screen sends people to the
connection, and a sentence in «محلّي» names the tab that holds the weekly report. Those links are
strings written far from this screen.

So a tab is not only a thing on this page — it is a destination other pages already promise. When
one is removed and its name is not redirected, every promise made to it silently lands on the
default tab instead. Nobody sees an error: the person is simply somewhere else, looking for a
setting that is not there, and the screen looks like it lost the feature.

THE RULE, IN TWO HALVES.

  · Every name that was ever a destination — `PaneLink` — must be either a tab that still exists
    or a key in `MOVED` that points at one. A name that is neither is a promise nothing keeps.
  · Every value in `MOVED` must be a real tab. Redirecting to a tab that no longer exists is the
    same defect one hop further along, and it is the one a rename makes easy.

WHAT THIS IS NOT. It does not check that the SECTION moved with the name — no static check can see
that a checkbox is rendered on the page it now points at. That is what the crossing test does
(`account_tabs.test.tsx`); this gate holds the part that a rename can break silently.

    python ci/check_a_tab_that_was_removed_still_has_somewhere_to_land.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ACCOUNT = ROOT / "apps" / "console" / "src" / "screens" / "Account.tsx"

PANE_TYPE = re.compile(r"export type Pane\s*=\s*([^;]+);")
LINK_TYPE = re.compile(r"export type PaneLink\s*=\s*([^;]+);")
MOVED_BLOCK = re.compile(r"export const MOVED[^{]*\{(.*?)\}", re.S)
MOVED_ENTRY = re.compile(r"(\w+)\s*:\s*'([^']+)'")

#: The tab list the screen actually renders, read from the ids in TABS.
TABS_BLOCK = re.compile(r"const TABS[^=]*=\s*\[(.*?)\n\];", re.S)
TAB_ID = re.compile(r"\{\s*id:\s*'([^']+)'")


def _names(union: str) -> list[str]:
    return re.findall(r"'([^']+)'", union)


def main() -> int:
    if not ACCOUNT.is_file():
        print("apps/console/src/screens/Account.tsx is missing — this gate cannot answer")
        return 1

    source = ACCOUNT.read_text(encoding="utf-8")
    pane = PANE_TYPE.search(source)
    link = LINK_TYPE.search(source)
    moved = MOVED_BLOCK.search(source)
    tabs = TABS_BLOCK.search(source)
    if not (pane and link and moved and tabs):
        # ONE OF THE FOUR IS GONE. This gate then knows nothing, and «knows nothing» has never
        # been the same as «fine» here.
        print("  \033[31m✘ Account.tsx no longer declares Pane, PaneLink, MOVED and TABS as this "
              "gate reads them — point it at what replaced them\033[0m")
        return 1

    panes = set(_names(pane.group(1)))
    links = set(_names(link.group(1)))
    rendered = set(TAB_ID.findall(tabs.group(1)))
    redirects = dict(MOVED_ENTRY.findall(moved.group(1)))

    problems: list[str] = []

    # A TAB IN THE TYPE THAT THE SCREEN NEVER RENDERS is a destination the strip cannot show.
    for name in sorted(panes - rendered):
        problems.append(f"«{name}» is a Pane but TABS never renders it — a destination with no tab")

    for name in sorted(rendered - panes):
        problems.append(f"TABS renders «{name}» but it is not a Pane — the type and the strip "
                        f"disagree")

    # EVERY OLD NAME MUST LAND. Either it is still a tab, or MOVED says where it went.
    for name in sorted(links - panes):
        if name not in redirects:
            problems.append(f"«{name}» is a link other screens may open and it is neither a tab "
                            f"nor in MOVED — it lands on the default and looks like a lost feature")

    for name, target in sorted(redirects.items()):
        if target not in rendered:
            problems.append(f"MOVED sends «{name}» to «{target}», which is not a tab — the "
                            f"redirect is one hop from nowhere")

    if problems:
        print("  \033[31m✘ «حسابي» has destinations that lead nowhere:\033[0m")
        for problem in problems:
            print(f"      \033[31m{problem}\033[0m")
        print("\n    Half the product links into these tabs by name. A name that no longer lands "
              "does not\n    fail — it opens the wrong tab, and the setting looks deleted. Do not "
              "exempt it here.")
        return 1

    print(f"  \033[32m✔ every «حسابي» destination lands: {len(rendered)} tab(s), "
          f"{len(redirects)} redirect(s)\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
