#!/usr/bin/env python3
"""IMAGES REACH THE SERVER FROM ghcr, AND FROM NOWHERE ELSE.

THE DECISION THIS ENFORCES. The developer builds and pushes to the registry; the server pulls from
the registry. Nothing travels from a personal machine into production — not a tarball, not a tunnel,
not an address that only resolves on the laptop that typed it. This is how it is done everywhere it
is done seriously, and the reason is not tidiness:

  * WHAT RAN CAN BE FOUND AGAIN. A digest in ghcr is fetchable by anyone with the token, months
    later, from any machine. An image that existed only in a laptop's docker daemon is gone the day
    that laptop is reinstalled — and with it the only copy of what production was running.
  * THE SERVER STOPS DEPENDING ON A PERSON BEING AWAKE. A node pointed at `127.0.0.1:5055` can only
    pull while a particular developer holds an ssh tunnel open. Reboot it at 3am and it comes back
    to a pod that cannot start, with nothing anywhere saying why.
  * AND A SECOND SERVER BECOMES POSSIBLE. The old arrangement made the product installable on
    exactly one machine on earth.

WHAT WENT WRONG, AND IT WAS FOUND BY READING THE CLUSTER RATHER THAN THE REPOSITORY. Every service
ran from `ghcr.io/engtamam/...` except one: `console` was running

    127.0.0.1:5055/raje3/console@sha256:865bc154…

which is a registry on a developer's laptop, written into a production Deployment. The repository
file was correct the whole time — `deploy/edge/console.yaml` names ghcr — because `ship.sh`
REWROTE the reference at ship time, on the node. So no gate reading the repository could see it,
every step printed success, and the console pod sat unable to pull. A shipped console had become
un-shippable, and the reason was invisible from every file in git.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE.

  1. No image reference anywhere names a numeric host or a loopback name. `ghcr.io/...` is a name
     the world can resolve; `127.0.0.1:5055/...` is a name exactly one machine can.
  2. No script moves an image to the node: no `docker save` into ssh, no `ctr images import`, no
     `docker load` on the far side.
  3. No script stands up a registry for the node to reach back into.

Third-party images from public registries — `caddy:2.8-alpine`, `postgres:16` — are untouched by
this. They are names the world resolves too. The rule is about WHERE, not about WHOSE.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

SEARCH = ("deploy", "ci", "apps", "services")
SKIP = ("node_modules", "dist", "build", ".venv", "__pycache__", ".claude", "platform")
SUFFIXES = (".sh", ".yaml", ".yml", ".py", ".json", ".ts", ".tsx", "")

# A REGISTRY ONLY ONE MACHINE CAN REACH.
#
# NARROWED TO IMAGE REFERENCES, NOT LOOSENED. `127.0.0.1:8000/healthz` in a Dockerfile HEALTHCHECK
# is a container talking to itself and is correct; every service here has one. So the scope is the
# places where an image is NAMED — `image:`, `repository:`, and the docker/ctr verbs that take one
# — rather than the pattern being weakened to spare the innocent lines.
AN_IMAGE_LINE = re.compile(
    r"(?:^|\s)(?:image|repository)\s*:|docker\s+(?:push|pull|tag|save|load)\b|"
    r"docker\s+build[^\n]*\s-t\s|ctr\s+images?\b")
A_PRIVATE_REGISTRY = re.compile(
    r"(?<![\w.-])(?:\d{1,3}(?:\.\d{1,3}){3}|localhost)(?::\d+)?/[a-z0-9][\w./-]*", re.IGNORECASE)

# MOVING AN IMAGE BY HAND. Each of these is a way to put a layer on the node without the node
# having pulled it, which is the thing being banned.
BY_HAND = (
    (re.compile(r"docker\s+save\b"), "`docker save` — the image is being carried, not pulled"),
    (re.compile(r"docker\s+load\b"), "`docker load` — an image is arriving as a file"),
    (re.compile(r"ctr\s+images?\s+import\b"), "`ctr images import` — a tarball is being unpacked "
                                             "into the node's own image store"),
    (re.compile(r"ssh\s[^|;&]*-R\s"), "an ssh reverse forward — the node is being given a way back "
                                      "into the machine that opened it"),
    (re.compile(r"docker\s+run[^\n]*\bregistry:\d"), "a registry container — the node is meant to "
                                                     "pull from this machine"),
)

# `--plain-http` only ever means one thing here: a registry with no certificate, which a public one
# cannot be.
PLAIN_HTTP = re.compile(r"--plain-http\b")


def _files():
    for top in SEARCH:
        base = ROOT / top
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not any(s in p.parts for s in SKIP):
                if p.suffix in SUFFIXES or p.name == "Dockerfile":
                    yield p


def main() -> int:
    bad: list[str] = []
    read = 0

    for path in sorted(_files()):
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        read += 1

        # This gate has to spell out what it forbids; it is the one file that may.
        if path.name == pathlib.Path(__file__).name:
            continue

        # A BACKSLASH IS NOT A HIDING PLACE. `docker run \<newline> ... registry:2` is one command,
        # and a gate that reads it as two lines finds neither half. Continuations are joined before
        # anything is matched — which is how `registry.sh` first slipped past this check.
        joined = re.sub(r"\\\n\s*", " ", text)
        for n, line in enumerate(joined.splitlines(), 1):
            if line.lstrip().startswith(("#", "//", "*")):
                continue
            m = A_PRIVATE_REGISTRY.search(line) if AN_IMAGE_LINE.search(line) else None
            if m:
                bad.append(f"{rel}:{n}: `{m.group(0)}` is a registry only one machine can reach. "
                           f"Images come from ghcr, so the server never depends on a laptop being "
                           f"awake — and so what ran can be found again next month")
            # CARRYING AN IMAGE IS SOMETHING ONLY A DEPLOY SCRIPT CAN DO. A check that greps for
            # `docker save` in order to assert its ABSENCE is not carrying anything, and the test
            # suite does exactly that — so the verbs are looked for where images actually move,
            # rather than the words being banned everywhere and then excused case by case.
            in_deploy = path.parts[len(ROOT.parts)] == "deploy" if len(path.parts) > len(ROOT.parts) else False
            for pattern, why in (BY_HAND if in_deploy else ()):
                if pattern.search(line):
                    bad.append(f"{rel}:{n}: {why}. The node pulls from ghcr; nothing is carried to "
                               f"it")
            if PLAIN_HTTP.search(line):
                bad.append(f"{rel}:{n}: `--plain-http` — a registry without a certificate is not a "
                           f"public one, so this is a pull from somebody's own machine")

    if not read:
        print(f"{C_R}no files read — this gate has nothing to check, which is not the same as "
              f"finding nothing wrong{C_N}")
        return 1

    if bad:
        print(f"{C_R}an image would reach the server from somewhere other than ghcr{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Build and push with  deploy/publish-images.sh  (it pins the digest it was")
        print("  given), commit the pin, and let the node pull it.")
        return 1

    print(f"{C_G}ok{C_N}  {read} files — every image the server runs comes from a registry the "
          f"world can reach")
    return 0


if __name__ == "__main__":
    sys.exit(main())
