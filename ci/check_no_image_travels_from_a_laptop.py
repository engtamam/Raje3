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
# `localhost` AND AN IPv4 WERE NOT THE ONLY WAYS TO NAME A MACHINE ONLY YOU CAN REACH.
# `host.docker.internal:5000/x` is the spelling Docker Desktop hands you, and it walked straight
# through. So do `*.local` (mDNS), a bare hostname with a port, and `::1`. The question this gate
# asks is «can the server resolve this without your laptop being awake», and the honest answer for
# every one of these is no.
#
# AND THE SENTENCE ABOVE NAMED «a bare hostname with a port» WHILE THE PATTERN DID NOT MATCH ONE.
# `buildbox:5000/raje3/console` — the shape you get the moment the registry moves off the loopback
# and onto the LAN machine beside it — passed. A comment that claims more than its pattern delivers
# is worse than no comment: the next reader checks the prose, sees the case covered, and stops.
#
# WHAT MAKES THE BARE HOSTNAME SAFE TO BAN IS THE DOT, AND THE PORT. A registry the world resolves
# has a dot in it (`ghcr.io`, `docker.io`, `registry.k8s.io`); a single label resolves only inside
# one network's own search domain. The port is REQUIRED rather than optional, and that is the whole
# of the false-positive defence: without it this would match `raje3/console:dev` in every
# `docker build -t` line in the repository and be wrong about more lines than it was right about.
#: THE PATH MUST CONTAIN A LETTER — `(?=[\w./-]*[a-z])`, a lookahead rather than a narrower
#: character class, so the rest of the shape (dots, slashes, digits — a real repo path has all
#: three) stays exactly as permissive as it needs to be. Without it `10.43.0.1/32` — a NetworkPolicy
#: egress rule's own CIDR, `cidr: 10.43.0.1/32`, `172.31.37.58/32` — read as `<ip>/<repo-path>`,
#: because a netmask suffix is itself `[a-z0-9][\w./-]*`: all digits, which this grammar cannot
#: tell apart from a one-character, all-numeric repository name. A real image reference always
#: has a letter in it (`raje3/console`, `engtamam/whatsapp-assistant`); a CIDR mask never does.
A_PRIVATE_REGISTRY = re.compile(
    r"(?<![\w.-])(?:"
    r"\d{1,3}(?:\.\d{1,3}){3}"            # an IPv4 literal
    r"|\[?::1\]?"                         # IPv6 loopback
    r"|localhost"
    r"|host\.docker\.internal"            # Docker Desktop's name for the machine running Docker
    r"|[a-z0-9][\w-]*\.local"             # mDNS: only resolvable on one LAN
    r")(?::\d+)?/(?=[\w./-]*[a-z])[a-z0-9][\w./-]*"
    r"|(?<![\w.-])[a-z][a-z0-9-]*:\d+/(?=[\w./-]*[a-z])[a-z0-9][\w./-]*",  # a single-label host, and a port
    re.IGNORECASE)

#: `REG="127.0.0.1:5055/raje3"` — a shell, YAML or env assignment whose value IS a private
#: registry. Naming one is the act; the line that later spends the name carries no evidence at all.
#:
#: THE REPOSITORY PATH IS REQUIRED, AND THAT IS THE DEFINITION RATHER THAN A CONCESSION. Without it
#: this matched `HOST = "0.0.0.0"` — a bind address, the opposite of a place to fetch from — and an
#: audit-sink URL in six test files, eighteen findings that were all wrong. A gate that cries wolf
#: eighteen times is a gate nobody reads the nineteenth time. `host:port/repo` is what a registry
#: reference IS; `host` alone is a machine, and this gate has no opinion about machines.
ASSIGNS_A_REGISTRY = re.compile(
    r"""(?:^|\s)[A-Za-z_][\w.-]*\s*[:=]\s*["']?"""
    r"""(?P<reg>(?:\d{1,3}(?:\.\d{1,3}){3}|\[?::1\]?|localhost|host\.docker\.internal"""
    r"""|[a-z0-9][\w-]*\.local)(?::\d+)?/(?=[\w./-]*[a-z])[a-z0-9][\w./-]*"""
    # The same single-label host, for the same reason: `REG="buildbox:5000/raje3"` is the assignment
    # form of the case the pattern above had been claiming to cover and did not. And the same
    # letter requirement as A_PRIVATE_REGISTRY above — `cidr: 10.43.0.1/32` is `key: value` too,
    # and without it every NetworkPolicy egress CIDR in the repo read as a registry assignment.
    r"""|[a-z][a-z0-9-]*:\d+/(?=[\w./-]*[a-z])[a-z0-9][\w./-]*)""", re.IGNORECASE)

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

        # NEITHER IS A VARIABLE, AND THAT IS THE SHAPE THIS FILE'S OWN HEADER DESCRIBES. Requiring
        # the registry and the image keyword on ONE line means
        #
        #     REG="127.0.0.1:5055/raje3"
        #     ...
        #     image: ${REG}/console@sha256:…
        #
        # passes both tests and fails the product: line one has the registry and no image keyword,
        # line two has the keyword and no registry. The gate was reading for a coincidence of
        # spelling rather than for the fact.
        #
        # So an assignment of a private registry to a name is itself reported, wherever the name is
        # later used — because there is no innocent reason to write one down. That keeps the rule
        # whole without a second, weaker rule about «variables that look like registries».
        for n, line in enumerate(joined.splitlines(), 1):
            if line.lstrip().startswith(("#", "//", "*")):
                continue
            if AN_IMAGE_LINE.search(line):
                continue                      # handled by the pass below, with its own message
            m = ASSIGNS_A_REGISTRY.search(line)
            if m:
                bad.append(f"{rel}:{n}: `{m.group('reg')}` is written into a name here. Wherever "
                           f"that name is used later, the image comes from a registry only one "
                           f"machine can reach — and the line that uses it looks innocent")
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
