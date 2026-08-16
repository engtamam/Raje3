#!/usr/bin/env python3
"""ONE GRAPH VERSION, AND NOT A WORD OF THE EMBEDDED SIGNUP META IS RETIRING.

TWO SHAPES, AND THE SECOND ONE HAS A DATE ON IT.

FIRST, THE DRIFT. `notification-service` was talking to Meta on two versions at once: it SENT on
Graph v26.0 (the platform's default) and ONBOARDED on v21.0 (our values file pinned it), while the
console initialised the JavaScript SDK on v21.0 as well. Nobody chose that. It is the same defect
as the deploy scripts: three places answering one question, and moving one of them updates one.

A Graph version is not cosmetic. Meta retires them on a schedule of about two years, and a call on
a retired version does not fail loudly — the field you asked for simply stops appearing, so the
shop is «connected» and cannot send, which is the exact symptom this product spent weeks chasing.

SECOND, THE DEADLINE. Embedded Signup v2 and v3 are both retired on 15 October 2026. What dies
with them is a vocabulary: `sessionInfoVersion` and `featureType` are parameters v4 does not
accept, and `only_waba_sharing` is a feature type v4 replaced. v4's `extras` is empty, and which
version the popup opens is decided by the Facebook Login for Business configuration behind
`config_id` — a setting on Meta's side, not a line of ours.

So the migration has an end state that can be CHECKED rather than remembered: those words are not
in our tree. A deadline that lives only in a comment is a deadline nothing enforces, and this one
falls due while the shop is mid-signup.

NO EXCEPTIONS TABLE. There is no file in this repository that has a good reason to name a retired
Embedded Signup parameter, and no second Graph version that anything here should be speaking.

WHAT THIS GATE CANNOT SEE, said plainly rather than implied: `platform/` is read only, and its own
defaults are its own. This gate reads OUR tree — what we pin, ship and build — and the day the
platform moves, the values here are one line each.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# THE ONE VERSION THIS PRODUCT SPEAKS. It is the platform's own default for both the sending and
# the onboarding adapters, so anything lower here means our two halves disagree with each other.
GRAPH = "v26.0"

# The vocabulary Meta retires on 2026-10-15 along with Embedded Signup v2 and v3. `featureType`
# and `sessionInfoVersion` are `extras` keys v4 rejects; `only_waba_sharing` is a feature type it
# replaced with `app_only_install`.
RETIRED = ("sessionInfoVersion", "session_info_version", "featureType", "feature_type",
           "only_waba_sharing", "whatsapp_business_app_onboarding")

ANY_GRAPH = re.compile(r"graph\.facebook\.com/(v\d+\.\d+)")
# A bare version pin — `VITE_META_GRAPH_VERSION || 'v21.0'`, `VITE_META_GRAPH_VERSION=v21.0`.
PINNED = re.compile(r"(?:META_GRAPH_VERSION|GRAPH_VERSION)\s*(?:\|\||=|:)[^\n]*?['\"=]?(v\d+\.\d+)")

# Where we say what we ship. `platform/` is excluded because it is read only and speaks for
# itself; build output is excluded because it is this same source, compiled.
SEARCH = ("apps", "deploy", "services", "ci")
SKIP = ("node_modules", "dist", "build", ".venv", "__pycache__", ".claude")
SUFFIXES = (".ts", ".tsx", ".py", ".yaml", ".yml", ".sh", ".json", ".example", "")


def _files():
    for top in SEARCH:
        base = ROOT / top
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or any(s in p.parts for s in SKIP):
                continue
            if p.suffix in SUFFIXES or p.name in ("Dockerfile", "target.env.example"):
                yield p
    for name in ("deploy/target.env.example",):
        p = ROOT / name
        if p.is_file():
            yield p


def main() -> int:
    bad: list[str] = []
    versions: dict[str, list[str]] = {}
    read = 0

    for path in sorted(set(_files())):
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            # REPORTED, NOT SKIPPED: a file this gate cannot read is a file it cannot clear, and
            # a version pin is exactly the one-line thing that hides in the file nobody opens.
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        read += 1

        # This gate necessarily spells the retired words out; it is the one file that may.
        is_self = path.name == pathlib.Path(__file__).name

        for n, line in enumerate(text.splitlines(), 1):
            if is_self or line.lstrip().startswith(("#", "//", "*")):
                continue
            for word in RETIRED:
                if word in line:
                    bad.append(f"{rel}:{n}: `{word}` belongs to Embedded Signup v2/v3, which Meta "
                               f"retires on 2026-10-15. v4 takes an empty `extras` and reads its "
                               f"version from the login configuration behind config_id")
            for m in ANY_GRAPH.finditer(line):
                versions.setdefault(m.group(1), []).append(f"{rel}:{n}")
            for m in PINNED.finditer(line):
                versions.setdefault(m.group(1), []).append(f"{rel}:{n}")

    if not read:
        print(f"{C_R}no files read — this gate has nothing to check, which is not the same as "
              f"finding nothing wrong{C_N}")
        return 1

    if not versions:
        # SILENCE IS NOT AGREEMENT. If nothing names a Graph version, the console's `FB.init` and
        # the onboarding adapter are each taking somebody else's default, which is how the two
        # drifted apart in the first place.
        bad.append("nothing in our tree names a Graph version — the console and the onboarding "
                   f"adapter would each inherit a default, and this gate exists because they "
                   f"inherited different ones. Pin {GRAPH}.")

    wrong = {v: where for v, where in versions.items() if v != GRAPH}
    if wrong:
        for v, where in sorted(wrong.items()):
            bad.append(f"speaks Graph {v}, but this product speaks {GRAPH}: " + ", ".join(where))

    if bad:
        print(f"{C_R}Meta's version is not one answer, or names something retired{C_N}")
        for line in bad:
            print(f"  {line}")
        return 1

    sites = sum(len(w) for w in versions.values())
    print(f"{C_G}ok{C_N}  Graph {GRAPH} in {sites} places, and no retired Embedded Signup "
          f"parameter in {read} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
