#!/usr/bin/env python3
"""EVERY IMAGE THIS PRODUCT RUNS IS PINNED BY DIGEST — including the two with no values file.

THE BLIND SPOT THIS CLOSES, AND THE QA SWEEP NAMED IT WITHOUT FINDING WHAT WAS IN IT.
`ci/check_deploy_wiring.py` walks `deploy/services/*.values.yaml`, and two things this product
cannot serve a single request without are deployed by raw manifests instead:

  * the CONSOLE — a static bundle behind `deploy/edge/console.yaml`;
  * the EDGE — Caddy, which terminates TLS and routes the domain at everything else.

`verify-fleet.sh` says so itself and then checks only that they are RUNNING. So the edge's image
was verified by nothing at all, and it was the one image in the fleet still named by a TAG:

    image: caddy:2.8-alpine

A tag is a name, and a name can be moved. `caddy:2.8-alpine` resolved to
`sha256:af32e973…` on the day this was written and is under no obligation to resolve there
tomorrow. Nothing here pulls on a schedule, so the change would not arrive at a moment anybody
chose — it would arrive at the next pod restart, the next node reboot, the next eviction. The one
pod every request in the product passes through would come back different, and the only record of
what it used to be would be gone with the pod that held it.

THIS IS THE SAME FAMILY AS THE CONSOLE'S `127.0.0.1:5055`, ONE LAYER OVER. That one was an address
nobody else could resolve; this is an address that resolves to whatever it likes. Both are images
the repository does not actually determine, and both hid in the same place: outside every gate,
because their deployment has no values file.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE.

  1. Every `image:` in a manifest under `deploy/` names a digest. Upstream or ours, public or
     private — there is no image in this product that should be free to change without a commit.
  2. An image from a registry that needs credentials declares `imagePullSecrets` in the same pod
     spec. Without it the pod does not fail loudly either: it sits in ImagePullBackOff, which
     reads as a broken registry rather than a missing line.

WHY NOT «pin ours and trust upstream». Because upstream is where the risk lives. Our images are
pushed by a script that reads the digest back from the registry and writes it down. Caddy's tag is
moved by strangers on their own schedule, for their own reasons, and we would learn about it from
a customer.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# A manifest, as opposed to a values file or an arbitrary yaml: it declares Kubernetes objects.
A_MANIFEST = re.compile(r"^kind:\s*\w+", re.M)

# `image: something`, ignoring a commented line. The value may be quoted.
AN_IMAGE = re.compile(r"^\s*image:\s*[\"']?([^\"'\s#]+)")

# Registries that will refuse an anonymous pull. ghcr is ours and private; the rest of the world's
# public registries are not the question here — rule 2 is about credentials, not about ownership.
NEEDS_CREDENTIALS = ("ghcr.io/",)


def main() -> int:
    bad: list[str] = []
    pinned = 0
    checked = 0

    files = sorted(DEPLOY.rglob("*.yaml")) + sorted(DEPLOY.rglob("*.yml"))
    if not files:
        print(f"{C_R}no manifests under deploy/ — this gate has nothing to check, which is not "
              f"the same as finding nothing wrong{C_N}")
        return 1

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            # REPORTED, NOT SKIPPED. An unreadable manifest is one this gate cannot clear, and an
            # image line is exactly the kind of thing that hides in the file nobody opens.
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        if not A_MANIFEST.search(text):
            continue                       # a values file; check_deploy_wiring.py owns those
        checked += 1

        declares_secret = "imagePullSecrets:" in text

        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            m = AN_IMAGE.match(line)
            if not m:
                continue
            ref = m.group(1)
            if "@sha256:" not in ref:
                bad.append(f"{rel}:{n}: `{ref}` is named by a tag. A tag can be moved by whoever "
                           f"owns it, and the change would arrive at the next restart rather than "
                           f"at a moment anybody chose — pin the digest")
                continue
            pinned += 1
            if ref.startswith(NEEDS_CREDENTIALS) and not declares_secret:
                bad.append(f"{rel}:{n}: `{ref.split('@')[0]}` needs credentials and this manifest "
                           f"declares no imagePullSecrets — the pod would sit in ImagePullBackOff, "
                           f"which reads as a broken registry rather than a missing line")

    if bad:
        print(f"{C_R}an image this product runs is not pinned to content{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  A digest for a public image:  docker buildx imagetools inspect <ref>")
        print("  Ours are written by deploy/publish-images.sh, from what the registry answered.")
        return 1

    print(f"{C_G}ok{C_N}  {pinned} images across {checked} manifests — every one pinned to content")
    return 0


if __name__ == "__main__":
    sys.exit(main())
