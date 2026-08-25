#!/usr/bin/env bash
# ==================================================================================================
#  pack.sh — build the bundle the server actually needs, and nothing else.
# --------------------------------------------------------------------------------------------------
#  THE SERVER CARRIES WHAT RUNS, NOT WHAT WE WRITE. The product's source lives inside the images,
#  built and sealed and pinned by digest; a box that also holds the repository is a box from which
#  the product itself can be taken, not merely its data. So this ships four things:
#
#      deploy/                our scripts, values files and seeds
#      platform/deploy/chart  the helm chart the values are rendered against
#      platform/deploy/k3s    upstream's bootstrap (k3s · calico · datastores · tls · store)
#      platform/deploy/server upstream's gen-secrets, update.sh, preflights
#      platform/tools/edge     the renderer that turns our edge.json into a Caddyfile
#
#  AND A VERSION STAMP, WHICH IS THE PART WE LEARNED THE HARD WAY. The old server held a hand-copied
#  tree that had drifted a full release behind: our new install script ran against an old bootstrap
#  that did not know about the postgres TLS secret, and the failure looked like a bug in the script.
#  Every bundle now carries the commit, the platform version and the build time — and the installer
#  prints them, so «what is on that machine» is a question with an answer.
#
#  Usage:
#    bash deploy/pack.sh                          # build dist/raje3-deploy.tar.gz
#    bash deploy/pack.sh --to root@8.213.51.70    # build AND upload (needs KEY=path/to.pem)
# ==================================================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="${OUT:-$ROOT/dist}"
NAME="raje3-deploy"
TARGET=""

C_G=$'\e[32m'; C_C=$'\e[36m'; C_D=$'\e[2m'; C_R=$'\e[31m'; C_N=$'\e[0m'
ok(){ echo -e "${C_G}  ✔ $*${C_N}"; }
die(){ echo -e "${C_R}  ✖ $*${C_N}" >&2; exit 1; }

while [ $# -gt 0 ]; do case "$1" in
  --to) TARGET="${2:-}"; shift 2;;
  -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
  *) die "unknown flag: $1";;
esac; done

[ -d "$ROOT/platform/deploy/chart" ] || die "platform/ is not checked out — the bundle would ship without a chart"

STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/$NAME/platform/deploy"

# OURS, MINUS WHAT THE SERVER MUST NEVER HOLD. `pinned/` is a local render, `dist/` is this output,
# and a stray .env is exactly the file somebody drops beside a script and forgets.
tar -C "$ROOT" -cf - \
    --exclude='deploy/pinned' --exclude='deploy/.install.conf' --exclude='*.env' --exclude='*.pem' \
    deploy | tar -C "$STAGE/$NAME" -xf -

# THEIRS, ONLY THE THREE DIRECTORIES THAT RUN. Not their services, not their docs, not their tests —
# base-services' own source has no more business on this box than ours does.
for d in chart k3s server; do
  tar -C "$ROOT/platform/deploy" -cf - "$d" | tar -C "$STAGE/$NAME/platform/deploy" -xf -
done

# AND THE EDGE RENDERER, which is not under deploy/ but is RUN at install time: bring-up turns our
# edge.json into a Caddyfile with it. Left out, the install finishes and the domain answers nothing
# — the failure is a warning in a step nobody rereads, not a crash.
mkdir -p "$STAGE/$NAME/platform/tools"
tar -C "$ROOT/platform/tools" -cf - edge | tar -C "$STAGE/$NAME/platform/tools" -xf -

# CRLF STRIPPED FROM EVERY SHELL SCRIPT, ALWAYS — this stage tars the WORKING TREE, not a git
# blob. .gitattributes forces `eol=lf` on commit, but that only normalizes what git STORES; a
# file edited on Windows keeps CRLF sitting on disk until something rewrites it (core.autocrlf is
# false here on purpose — a repo that silently rewrites line endings on checkout is its own class
# of surprise). The server proved this the hard way: `set -uo pipefail\r` reads "pipefail" as an
# invalid option, `dirname "$0"` returns a path with a `\r` baked into it, and the failure looks
# like a broken script when the script was correct all along. Stripping here means every install,
# from any operator's machine in any line-ending state, ships bytes bash actually runs.
find "$STAGE/$NAME" -name '*.sh' -exec sed -i 's/\r$//' {} +

# THE STAMP. Read here, where git exists — the server has no repository to ask.
COMMIT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
DIRTY=""; git -C "$ROOT" diff --quiet 2>/dev/null || DIRTY=" (uncommitted changes)"
PLATFORM="$(git -C "$ROOT" submodule status platform 2>/dev/null | awk '{print $3}' | tr -d '()' || echo unknown)"
BUILT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$STAGE/$NAME/VERSION" <<TXT
raje3-deploy
commit:   $COMMIT$DIRTY
platform: ${PLATFORM:-unknown}
built:    $BUILT
TXT

mkdir -p "$OUT"
TARBALL="$OUT/$NAME.tar.gz"
tar -C "$STAGE" -czf "$TARBALL" "$NAME"
SIZE="$(du -h "$TARBALL" | cut -f1)"
ok "built $TARBALL ($SIZE) — commit $COMMIT, platform ${PLATFORM:-unknown}"

# A DIRTY TREE IS A BUNDLE NOBODY CAN REPRODUCE. Not fatal — this is how a fix gets to a pilot box
# in a hurry — but said out loud, because «which commit is on the server» must stay answerable.
[ -n "$DIRTY" ] && echo -e "${C_D}  note: built from a working tree with uncommitted changes${C_N}"

if [ -n "$TARGET" ]; then
  : "${KEY:?set KEY=/path/to/key.pem to upload}"
  echo -e "${C_C}  ▸ uploading to $TARGET${C_N}"
  scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new "$TARBALL" "$TARGET:/tmp/$NAME.tar.gz"
  # UNPACKED INTO A FIXED PATH, replacing what was there. A bundle that unpacks BESIDE the old one
  # leaves two trees on the box and a coin-toss about which the next person runs.
  #
  # SUDO'D, NOT PLAIN — /opt is root-owned and the login user on a stock cloud image (ubuntu,
  # debian, ...) is never root itself (root SSH login is refused outright on these AMIs). A plain
  # `ssh $TARGET "mkdir -p /opt/..."` reads as a broken box; the box is fine, the command just
  # never had permission to write there. Wrapped in one `sudo bash -c "..."` so the whole chain
  # runs under one elevation, not five separate password/NOPASSWD checks.
  ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$TARGET" \
    "sudo bash -c \"set -e; rm -rf /opt/raje3.new && mkdir -p /opt/raje3.new \
     && tar -C /opt/raje3.new -xzf /tmp/$NAME.tar.gz --strip-components=1 \
     && rm -rf /opt/raje3.prev && { [ -d /opt/raje3 ] && mv /opt/raje3 /opt/raje3.prev || true; } \
     && mv /opt/raje3.new /opt/raje3 && rm -f /tmp/$NAME.tar.gz && cat /opt/raje3/VERSION\""
  ok "unpacked at /opt/raje3 (previous kept at /opt/raje3.prev)"
  echo -e "${C_D}  next: ssh $TARGET 'cd /opt/raje3 && sudo bash deploy/install.sh'${C_N}"
fi
