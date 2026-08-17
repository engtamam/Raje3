#!/usr/bin/env python3
"""THE SAME DIGEST MUST CARRY THE SAME TAG EVERYWHERE IT IS WRITTEN.

WHAT THIS FOUND, AND NO GATE COULD SEE IT (د-5).

    deploy/k3s/edge.yaml:101      caddy:2.8.4-alpine@sha256:af32e973…
    deploy/edge/deployment.yaml:46  caddy:2.8-alpine@sha256:af32e973…

The same sixty-four hex characters, two different version labels. Nothing runs wrong — the digest
is what the kubelet resolves and the tag beside it is decoration — so every check passed and the
cluster was correct all along. The damage is entirely to the person reading: they diff the two
files, see `2.8.4` against `2.8`, and conclude the edge runs two versions. Or worse, they trust
the label, believe the pin is on a moving tag, and "fix" the one that was already right.

A PIN IS TWO CLAIMS AND ONLY ONE OF THEM IS ENFORCED. `@sha256:…` says WHAT runs and is checked by
the registry on every pull. `caddy:2.8-alpine` says WHICH VERSION that is, and is checked by
nobody — it is the only part a human reads, and the only part that can be wrong for years.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. Group every `name:tag@digest` reference across
`deploy/` by digest. A digest seen with two different tags fails. There is no legitimate reason
for one image to be labelled two ways in one repository — if the versions really differ, the
digests differ too, and this says nothing.
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# `repo/name:tag@sha256:<64 hex>` — the tag is the part this gate is about.
PINNED = re.compile(r"([A-Za-z0-9._/\-]+):([A-Za-z0-9._\-]+)@(sha256:[0-9a-f]{64})")


def main() -> int:
    if not DEPLOY.is_dir():
        print(f"{C_R}no deploy/ — this gate checked nothing, and an empty set is not "
              f"agreement{C_N}")
        return 1

    # digest -> {(name, tag)} -> [where]
    seen: dict[str, dict[tuple[str, str], list[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(list))
    unreadable: list[str] = []

    for path in sorted(DEPLOY.rglob("*")):
        if not path.is_file() or path.suffix not in (".yaml", ".yml", ".sh", ".json"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append(f"{rel}: cannot read it — {exc}")
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for name, tag, digest in PINNED.findall(line):
                seen[digest][(name, tag)].append(f"{rel}:{n}")

    if unreadable:
        print(f"{C_R}files this gate could not read — «could not tell» is not «nothing "
              f"found»{C_N}")
        for line in unreadable:
            print(f"  {line}")
        return 1

    bad: list[str] = []
    for digest, labels in sorted(seen.items()):
        if len(labels) < 2:
            continue
        shown = "; ".join(f"`{n}:{t}` at {', '.join(w)}" for (n, t), w in sorted(labels.items()))
        bad.append(f"{digest[:19]}… is labelled {len(labels)} different ways — {shown}. One "
                   f"image, one version: whichever label is wrong is the one a person will "
                   f"believe, because the digest is unreadable and the tag is not")

    if bad:
        print(f"{C_R}one digest, two version labels{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Make them agree on the tag the digest actually is.")
        return 1

    if not seen:
        print(f"{C_R}no pinned image reference found anywhere under deploy/ — either they moved "
              f"or this gate no longer recognises them, and an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {len(seen)} distinct digests, each labelled one way")
    return 0


if __name__ == "__main__":
    sys.exit(main())
