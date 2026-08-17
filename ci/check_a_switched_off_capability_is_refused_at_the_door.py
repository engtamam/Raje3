"""A capability the product switches off is refused by the server, not only hidden by the screen.

WHAT THIS PROTECTS. «رمز على الجهاز» — an employee who proves himself with four digits on a shared
tablet instead of signing in — is built end to end and switched OFF (`PIN_OPERATORS_ENABLED`). The
easy way to switch something off is to stop drawing the control, and that is not switching it off:
the route stays live for a stale tab, a queued request, a replayed one, or anybody who reads our
own API. A flag that only changes a screen is a note about an intention.

So the rule is a pair, and BOTH halves are checked here:

  1. the door reads the flag and refuses while it is false;
  2. the screen learns the answer FROM THE SERVER rather than hard-coding «off» — otherwise turning
     it on would need a console release, which is not a switch either.

NO EXCEPTIONS TABLE. A flag that governs a screen and not a route is the defect this file is named
after; there is no version of it that is fine.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Each entry: the flag, the file whose route must read it, and the console file that must be told.
FLAGS = [
    {
        "flag": "PIN_OPERATORS_ENABLED",
        "door": ROOT / "services" / "operations" / "app" / "api" / "v1" / "staff.py",
        "wire": "pin_operators_enabled",
        "screen": ROOT / "apps" / "console" / "src" / "screens" / "Team.tsx",
        "what": "«رمز على الجهاز» — the shared-tablet employee",
    },
]


def _read(path: pathlib.Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
        return None


def main() -> int:
    if not FLAGS:
        # SILENCE IS NOT AGREEMENT: an empty list means somebody removed the subject, not that the
        # rule holds.
        print("no switched-off capabilities declared — this gate needs re-pointing")
        return 1

    bad: list[str] = []
    for entry in FLAGS:
        for key in ("door", "screen"):
            if not entry[key].exists():
                print(f"cannot find {entry[key].relative_to(ROOT).as_posix()} — "
                      "this gate needs re-pointing")
                return 1
        door = _read(entry["door"])
        screen = _read(entry["screen"])
        if door is None or screen is None:
            return 1

        if entry["flag"] not in door:
            bad.append(f"{entry['door'].relative_to(ROOT).as_posix()} · the door never reads "
                       f"`{entry['flag']}`, so {entry['what']} stays callable while it is off")
        if entry["wire"] not in door:
            bad.append(f"{entry['door'].relative_to(ROOT).as_posix()} · the read does not carry "
                       f"`{entry['wire']}`, so the screen cannot be told")
        # THE NAME IN A TYPE IS NOT A READ, and a first version of this check accepted one.
        # `call<{ …; pin_operators_enabled?: boolean }>` declares the field and can sit above a body
        # that hard-codes `false` — so the substring was present, the gate was green, and the switch
        # had quietly become a console constant again. It looks for the field being TAKEN OFF the
        # answer.
        if f".{entry['wire']}" not in screen:
            bad.append(f"{entry['screen'].relative_to(ROOT).as_posix()} · the screen does not read "
                       f"`{entry['wire']}` off the answer — turning it on would need a release")

    if bad:
        print("A capability is switched off in the screen alone:")
        for line in bad:
            print("  " + line)
        print("\nA stale tab, a queued request or a replay reaches the route regardless. The flag "
              "must be read where the act happens.")
        return 1
    print(f"{len(FLAGS)} switched-off capability(ies): refused at the door and reported to the "
          "screen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
