#!/usr/bin/env bash
# Build, ship, pin, deploy and VERIFY one service — in one command.
#
#   ./deploy/ship.sh portal
#   ./deploy/ship.sh reminders operations       # several, in order
#   FAST=1 ./deploy/ship.sh operations          # push layers, not the whole image
#
# FAST=1 — THE SAME SIX STEPS, WITH STEP 4 DONE BY THE REGISTRY.
#
# `docker save | ssh` transfers the WHOLE image every time: ninety megabytes over an SSH tunnel
# because one Python file changed. The interpreter, the OS and the dependencies are identical to
# the copy already on the node, and they travel again anyway — a tarball has no idea what the other
# end already has.
#
# A registry does. `docker push` sends only the layers the destination is missing, and our code is
# the LAST layer of the Dockerfile precisely so a source edit rebuilds nothing else: kilobytes
# instead of ninety megabytes, seconds instead of minutes.
#
# NOTHING ABOUT THE PIN CHANGES. The image is still resolved by digest, still verified against the
# running pod's imageID at step 6. The registry is a faster road, not a looser rule — and the
# digest a registry reports for a pushed image is the MANIFEST digest, which is not the same string
# `docker build -q` prints, so it is read back from the push rather than assumed.
#
# Run `./deploy/registry.sh` once to stand it up on the node.
#
# WHY THIS EXISTS. The same six steps were run by hand for every service, and each one failed in a
# different way at least once:
#
#   the image was built before the code was added        -> a route 404ing on a running pod
#   the import was piped to /dev/null                    -> "imported" printed, nothing imported
#   containerd stored it by TAG, not by digest           -> ImagePullBackOff on a pinned deploy
#   the values file synced after the rollout, not before -> "rolled" against a two-version-old pin
#   rollout restart was used to pick up a new image      -> restarted the OLD image, cleanly
#   the pod was on the old digest and nobody looked      -> a proof that returned yesterday's numbers
#
# None of those is interesting. All of them cost an hour. This script does the steps in the only
# order that works and refuses to continue when one of them did not happen.
#
# NO `set -e`. Each phase reports and the script decides — `set -e` turns a diagnosable failure
# into a silent exit, which is the shape half the list above already has.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
REMOTE="${REMOTE:-tamam@127.0.0.1}"
PORT="${PORT:-2224}"
NS="${NS:-base-services}"
# KEEPALIVES, BECAUSE THE VERIFY STEP IS THE LONGEST QUIET MOMENT IN THE RUN.
#
# Between the rollout and the digest read the connection can sit idle long enough for something in
# the middle to drop it, and the failure surfaces as «Connection closed» during VERIFY — which
# reads as "the image did not take" about an image that took. Twice today that sent me chasing a
# rollout that had already succeeded.
#
# ServerAliveInterval keeps the channel warm; ServerAliveCountMax lets it survive a slow moment
# rather than giving up on the third. ConnectTimeout fails a genuinely unreachable host fast
# instead of hanging the whole ship.
# AND THE IMAGE PUSH IS WHERE THIS LINK DIES. A service image is hundreds of megabytes over a
# forwarded port, and three separate ships failed mid-transfer with "Connection timed out" — the
# tunnel gives up under sustained load long before the host is in trouble (measured: the host was
# idle with 2.7G free each time). 30 keepalives at 15s carries a four-minute stall without
# dropping the channel, which is longer than any pause this link has produced.
SSH=(ssh -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=30
     -o ConnectTimeout=20 -o TCPKeepAlive=yes -p "$PORT" "$REMOTE")

red(){ printf '\e[31m✗ %s\e[0m\n' "$*" >&2; }
yel(){ printf '\e[33m⚠ %s\e[0m\n' "$*"; }
grn(){ printf '\e[32m✔ %s\e[0m\n' "$*"; }
say(){ printf '\n\e[1m▸ %s\e[0m\n' "$*"; }

REG_PORT="${REG_PORT:-5055}"

# The tunnel that carries a push, opened for the length of this command and closed after it.
#
# NOT LEFT RUNNING. A forwarded port that outlives the script is a socket somebody finds open next
# week and cannot explain — and the one on 8080 already taught us what a stale forward costs: it
# held the port, answered nothing, and every screen in the console reported 502 from a cluster that
# was serving 200.
FAST_CTL="${TMPDIR:-/tmp}/raje3-ship-registry.sock"

registry_answers() {
  curl -fsS -m 5 -o /dev/null "http://127.0.0.1:$REG_PORT/v2/" 2>/dev/null
}

# THE FORWARD RUNS THE OTHER WAY — `-R`, not `-L`.
#
# The registry lives HERE, beside the daemon, because Docker Desktop's daemon is in its own Linux
# VM: the `127.0.0.1` it dials is that VM's loopback, so a registry on the node reached through a
# local forward is unreachable to it no matter how well the forward works. Every push died on
# "connection refused" against a port curl answered from the same shell.
#
# So the push is local and instant, and the NODE reaches back through this reverse forward when
# containerd pulls — the direction that has to carry the layers anyway.
#
# AND IT ASKS THE REGISTRY, NOT THE SOCKET FILE. An earlier version took the control socket's
# existence as proof the tunnel was up, so a run that died between opening and cleaning it left the
# file behind and the next run pushed into nothing.
open_registry_tunnel() {
  registry_answers || {
    red "the registry is not running on this machine — run ./deploy/registry.sh once"
    return 1
  }
  # Already carried by another shell? Then it is already as good as ours.
  "${SSH[@]}" "curl -fsS -m 3 -o /dev/null http://127.0.0.1:$REG_PORT/v2/" 2>/dev/null && return 0
  ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -M -S "$FAST_CTL" -f -N \
      -R "127.0.0.1:$REG_PORT:127.0.0.1:$REG_PORT" -p "$PORT" "$REMOTE" 2>/dev/null
  for _ in 1 2 3 4 5; do
    "${SSH[@]}" "curl -fsS -m 3 -o /dev/null http://127.0.0.1:$REG_PORT/v2/" 2>/dev/null && return 0
    sleep 1
  done
  return 1
}

close_registry_tunnel() {
  [ -S "$FAST_CTL" ] || return 0
  ssh -S "$FAST_CTL" -O exit "$REMOTE" >/dev/null 2>&1
}
trap close_registry_tunnel EXIT

# Step 4, done by the registry instead of by a tarball.
#
# IT PRINTS THE MANIFEST DIGEST ON STDOUT, and the caller re-pins to it. That is the correction
# this path needed twice: `docker build -q` prints the CONFIG digest, and `ctr images tag
# <src> docker.io/raje3/svc@sha256:<config>` happily creates a NAME that merely looks like a digest
# reference. containerd never checks that the digest in a name matches the content, so kubelet
# resolved the name, ran whatever was behind it, and reported an imageID from a build two hours
# old — a deployment pinned to a number that described nothing.
#
# The registry's manifest digest is the real content address. Pin THAT, reference the image by it,
# and a pod running the wrong bytes becomes impossible rather than merely unlikely.
ship_image_fast() {
  local svc="$1" digest="$2"
  # 127.0.0.1 AND NOT `localhost`, FOR THE THIRD TIME IN ONE NIGHT. `localhost` resolves to ::1
  # first, the forward binds 127.0.0.1, and the push dies on `dial tcp [::1]:5055: i/o timeout`
  # after thirty seconds of retries. Both are "insecure by default" to Docker, so the literal
  # address costs nothing and removes a resolution order from the critical path.
  #
  # AND THE TAG CARRIES THE BUILD, NEVER A FIXED WORD. `:ship` was reused every time, so a pull
  # that found the name already in containerd was satisfied by whatever content it pointed at —
  # the deployment referenced the new digest, the pod reported the OLD one, and step 6 caught a
  # rollout that had rolled nothing. This is the same family as the failure this script's header
  # names ("containerd stored it by TAG"), and a unique tag closes it for good.
  local tag="${digest#sha256:}"
  local ref="127.0.0.1:$REG_PORT/raje3/$svc:${tag:0:16}"

  open_registry_tunnel || {
    red "$svc: the node cannot reach the registry — run ./deploy/registry.sh once"; return 1
  }

  # ALREADY ON THE NODE? THEN SAY SO AND STOP. A ship that failed at the pull, at the roll, or at
  # the verify has usually left the image sitting in containerd — and re-pushing three hundred
  # megabytes to prove what a one-line query answers is how a five-minute repair became an hour
  # tonight. This is the resume the whole path was missing.
  local have
  have="$("${SSH[@]}" "sudo -n k3s ctr images ls -q 2>/dev/null | grep -m1 '^127.0.0.1:$REG_PORT/raje3/$svc@'" 2>/dev/null | tr -d '
')"
  if [ -n "$have" ] && docker image inspect "raje3/$svc:ship" >/dev/null 2>&1; then
    # It is only the same build if the LOCAL image would push to the same digest, so this is a
    # hint and never a claim: we still push below, and Docker sends only the missing layers —
    # which for an unchanged image is nothing at all.
    say "$svc · the node already holds an image for this service — pushing only what changed"
  fi

  docker tag "raje3/$svc:ship" "$ref" || return 1
  # ONLY THE MISSING LAYERS TRAVEL. Our Dockerfiles copy the source last, so a code edit is one
  # small layer and everything under it is already on the node.
  local pushed
  pushed="$(docker push "$ref" 2>&1 | sed -n 's/.*digest: \(sha256:[0-9a-f]*\).*/\1/p' | tail -1)"
  case "$pushed" in
    sha256:*) ;;
    *) red "$svc: push to the registry failed — is it up? (./deploy/registry.sh)"; return 1 ;;
  esac

  # PULLED INTO CONTAINERD BY THAT DIGEST, which is a local copy on the node and costs nothing over
  # the wire. kubelet reads containerd, not the registry, so a pushed image nothing pulled is an
  # image the pod cannot see — and pulling BY DIGEST is what makes the name and the content the
  # same fact rather than two.
  # RETRIED, AND THE TUNNEL REBUILT BETWEEN TRIES. This single step cost four ships in one evening.
  # The layers travel back over the forward while the node pulls, and a forwarded port under
  # sustained load is the least reliable thing in this pipeline — it dropped mid-pull three times
  # with the host idle and 2.7G free. The old code took ONE failure as final and threw away a build
  # and a push that had both succeeded.
  #
  # THE TWO REASONS ARE SEPARATED, because they need different answers from whoever reads this:
  # "the forward died" is worth retrying, "the digest is not there" is not.
  local pull_ok=0 attempt
  for attempt in 1 2 3; do
    if ! "${SSH[@]}" "curl -fsS -m 5 -o /dev/null http://127.0.0.1:$REG_PORT/v2/" 2>/dev/null; then
      say "$svc · the registry forward dropped — rebuilding it (try $attempt/3)"
      close_registry_tunnel
      open_registry_tunnel || { sleep 3; continue; }
    fi
    if "${SSH[@]}" "sudo -n k3s ctr images pull --plain-http 127.0.0.1:$REG_PORT/raje3/$svc@$pushed >/dev/null 2>&1; sudo -n k3s ctr images ls -q | grep -qx 127.0.0.1:$REG_PORT/raje3/$svc@$pushed"; then
      pull_ok=1
      break
    fi
    say "$svc · the pull did not settle — retrying ($attempt/3)"
    sleep $(( attempt * 3 ))
  done
  if [ "$pull_ok" -ne 1 ]; then
    red "$svc: the image is NOT in containerd under $pushed after 3 tries"
    red "   the build and the push SUCCEEDED — re-running resumes from here without rebuilding"
    return 1
  fi
  # The caller re-pins the values file to this, and points the repository at the registry.
  printf '%s' "$pushed"
  return 0
}

ship_one() {
  local svc="$1"
  local dir="$ROOT/services/$svc"
  local values="$ROOT/deploy/services/$svc.values.yaml"
  [ -d "$dir" ]    || { red "$svc: no services/$svc"; return 1; }
  [ -f "$values" ] || { red "$svc: no deploy/services/$svc.values.yaml"; return 1; }

  # ── 1. tests, before anything is built ───────────────────────────────────────────────────────
  # Cheapest gate first. Building an image from code that does not pass its own tests wastes four
  # minutes to discover something that took four seconds.
  say "$svc · 1/6 tests"
  if ! (cd "$dir" && python3 -m pytest tests/unit -q 2>&1 | tail -2); then
    red "$svc: unit tests failed — nothing built, nothing shipped"; return 1
  fi

  # ── 2. build ─────────────────────────────────────────────────────────────────────────────────
  say "$svc · 2/6 build"
  local digest
  digest="$(cd "$dir" && docker build -q -t "raje3/$svc:ship" . 2>&1 | tail -1)"
  case "$digest" in
    sha256:*) grn "built ${digest:0:26}…" ;;
    *) red "$svc: build failed: $digest"; return 1 ;;
  esac

  # ── 3. pin, and run OUR guards against the pin ───────────────────────────────────────────────
  # Before the image travels: a values file that fails a guard is a rollout that should not happen,
  # and finding that out after a 90-second transfer is 90 seconds wasted every time.
  say "$svc · 3/6 pin + guards"
  local old
  old="$(grep -m1 'digest:' "$values" | sed -E 's/.*"([^"]*)".*/\1/')"
  if [ "$old" = "$digest" ]; then
    yel "already pinned to this digest — the code did not change since the last ship"
  fi
  sed -i "s|$old|$digest|" "$values"
  python3 "$ROOT/ci/check_deploy_wiring.py" >/dev/null 2>&1 || {
    red "$svc: deploy-wiring guard failed"
    python3 "$ROOT/ci/check_deploy_wiring.py" 2>&1 | tail -8
    sed -i "s|$digest|$old|" "$values"   # leave the tree as we found it
    return 1
  }
  grn "pinned and guards green"

  # ── 4. ship the image, and PROVE it arrived under its digest ─────────────────────────────────
  # The tag→digest step is what makes a digest-pinned deploy resolvable at all: `ctr images import`
  # stores by TAG, so kubelet tries the registry and fails with "pull access denied".
  say "$svc · 4/6 ship image"
  if [ "${FAST:-0}" = "1" ]; then
    local manifest
    manifest="$(ship_image_fast "$svc" "$digest")" || return 1
    # RE-PINNED TO WHAT THE REGISTRY STORES, and the repository moved with it. A digest is an
    # address inside a repository; pinning the registry's manifest digest under `docker.io/...`
    # would name content that repository does not contain.
    sed -i "s|$digest|$manifest|" "$values"
    sed -i "s|repository: docker.io/raje3/$svc|repository: 127.0.0.1:$REG_PORT/raje3/$svc|" "$values"
    digest="$manifest"
    python3 "$ROOT/ci/check_deploy_wiring.py" >/dev/null 2>&1 || {
      red "$svc: deploy-wiring guard failed after re-pinning to the registry digest"
      python3 "$ROOT/ci/check_deploy_wiring.py" 2>&1 | tail -8
      return 1
    }
  elif ! docker save "raje3/$svc:ship" | "${SSH[@]}" \
        "cat > /tmp/$svc.tar && sudo -n k3s ctr images import /tmp/$svc.tar >/dev/null 2>&1 \
         && sudo -n k3s ctr images tag docker.io/raje3/$svc:ship docker.io/raje3/$svc@$digest \
            >/dev/null 2>&1; sudo -n k3s ctr images ls -q | grep -qx docker.io/raje3/$svc@$digest"; then
    red "$svc: the image is NOT in containerd under $digest — the pod would ImagePullBackOff"
    return 1
  fi
  grn "image present under its digest"

  # ── 5. sync the declaration BEFORE rolling ───────────────────────────────────────────────────
  # In that order, always. A rollout reads the values file on the SERVER; syncing afterwards means
  # helm renders the previous pin and reports success about it.
  say "$svc · 5/6 sync + roll"
  if ! tar czf - -C "$ROOT" "deploy/services/$svc.values.yaml" deploy/hooks deploy/server 2>/dev/null \
       | "${SSH[@]}" "cd ~/raje3 && tar xzf - 2>/dev/null && chmod +x deploy/hooks/*.sh \
         && grep -q '$digest' deploy/services/$svc.values.yaml"; then
    red "$svc: the values file on the server does not carry the new digest"; return 1
  fi
  # OURS, NOT THEIRS. deploy/server/update.sh is our copy of the platform's rollout, and the one
  # thing it adds is fetching the images in parallel before the sequential loop needs them — a single
  # image took 3m50s on this link, and nineteen in single file took over an hour. The rollout logic
  # underneath is unchanged, so a diff against theirs stays short.
  "${SSH[@]}" "cd ~/raje3 && sudo -n PRODUCT_NAME=raje3 CHART=platform/deploy/chart \
     VALUES_DIR=deploy/services bash deploy/server/update.sh --only $svc 2>&1 | tail -2"

  # ── 6. verify the ARTIFACT, not the report ───────────────────────────────────────────────────
  say "$svc · 6/6 verify"
  local running=""
  for _ in $(seq 1 40); do
    running="$("${SSH[@]}" "kubectl -n $NS get pods --no-headers 2>/dev/null \
      | awk '/^$svc-[0-9a-f]/ && \$3==\"Running\" && \$2==\"1/1\" {print \$1; exit}'")"
    [ -n "$running" ] && break
    sleep 15
  done
  if [ -z "$running" ]; then
    red "$svc: no ready pod after 10 minutes"
    "${SSH[@]}" "kubectl -n $NS get pods --no-headers | grep '^$svc-'; \
      kubectl -n $NS logs \$(kubectl -n $NS get pods --no-headers | awk '/^$svc-/{print \$1;exit}') \
      --tail=20 2>&1 | tail -12"
    return 1
  fi
  local live
  live="$("${SSH[@]}" "kubectl -n $NS get pod $running \
      -o jsonpath='{.status.containerStatuses[0].imageID}'" | sed 's/.*@//')"
  if [ "$live" != "$digest" ]; then
    red "$svc: RUNNING ${live:0:26}… but shipped ${digest:0:26}…"
    # TWO DIGESTS TELL NOBODY WHY. This exact line appeared four times tonight and each time the
    # next twenty minutes went on asking the cluster what it already knew — so it asks now, once,
    # and prints the ONE fact that separates the causes.
    local why
    why="$("${SSH[@]}" "kubectl -n $NS get events --sort-by=.lastTimestamp 2>/dev/null         | grep -Ei 'operations|$svc' | grep -Ei 'Failed|BackOff|Error' | tail -2" 2>/dev/null)"
    if [ -n "$why" ]; then
      printf '   %s
' "$why"
      red "   the new pod could not START — the image is pinned but not runnable on the node"
      red "   almost always: the pull never landed. Re-run; the build and push are reused."
    else
      red "   the deployment still references the old image — the values sync did not apply."
      red "   fix: re-run this command (it re-syncs), rather than 'rollout restart', which"
      red "        re-pulls whatever the deployment ALREADY points at."
    fi
    return 1
  fi
  grn "$svc is running the image this command built"
  return 0
}

# ══ shipping SEVERAL, in the shape the work actually has ═══════════════════════════════════════
#
# One service at a time was four services waiting on each other for nothing: each one's build, its
# transfer and its rollout are independent of the next one's, and the only genuinely shared step —
# the deploy-wiring guard — was being run once PER SERVICE over the same unchanged repository.
#
# THE PHASES, AND WHY EACH BOUNDARY IS WHERE IT IS:
#
#   A. test + build      PARALLEL. Nothing outside this machine is touched, so a failure here costs
#                        only itself. Every service's digest is collected before anything travels.
#   B. pin + guard       ONCE, over the whole tree. The guard reads every values file and every
#                        manifest — running it per service asked the same question four times and
#                        answered it four times. And it must see ALL the new pins together: two
#                        services can be individually consistent and jointly wrong.
#   C. ship images       PARALLEL. Layers to the registry, then a local pull on the node.
#   D. sync + roll       ONCE, `--only a,b,c`. Helm's own wait is the cost here, and one wait for
#                        four services is not four waits — the rollouts overlap.
#   E. verify            PARALLEL, and unchanged: the pod's imageID against the digest WE built.
#
# NOTHING WAS TRADED AWAY FOR THE SPEED. Tests still precede every build, the guard still precedes
# every transfer, the values file still reaches the server before the rollout reads it, and the
# artifact is still checked rather than the report. The order is identical; only the waiting is
# gone.
ship_many() {
  local svcs=("$@") svc rc=0
  declare -A DIGEST=()

  # ── A. test + build, in parallel ─────────────────────────────────────────────────────────────
  say "1/5 tests + build · ${#svcs[@]} in parallel"
  local tmp; tmp="$(mktemp -d)"
  for svc in "${svcs[@]}"; do
    (
      dir="$ROOT/services/$svc"
      [ -d "$dir" ] || { echo "no services/$svc" > "$tmp/$svc.err"; exit 1; }
      (cd "$dir" && python3 -m pytest tests/unit -q >"$tmp/$svc.test" 2>&1) || {
        echo "unit tests failed" > "$tmp/$svc.err"; exit 1; }
      d="$(cd "$dir" && docker build -q -t "raje3/$svc:ship" . 2>&1 | tail -1)"
      case "$d" in
        sha256:*) printf '%s' "$d" > "$tmp/$svc.digest" ;;
        *) echo "build failed: $d" > "$tmp/$svc.err"; exit 1 ;;
      esac
    ) &
  done
  wait

  for svc in "${svcs[@]}"; do
    if [ -f "$tmp/$svc.err" ]; then
      red "$svc: $(cat "$tmp/$svc.err")"
      [ -f "$tmp/$svc.test" ] && tail -3 "$tmp/$svc.test"
      rc=1
    else
      DIGEST[$svc]="$(cat "$tmp/$svc.digest")"
      grn "$svc built ${DIGEST[$svc]:0:26}…"
    fi
  done
  # NOTHING SHIPS IF ANY BUILD FAILED. Half a fleet on a new digest and half on the old one is the
  # state nobody can reason about afterwards — least of all at three in the morning.
  [ "$rc" -eq 0 ] || { rm -rf "$tmp"; return 1; }

  # ── B. pin every one, then guard ONCE ────────────────────────────────────────────────────────
  say "2/5 pin + guards"
  declare -A OLD=()
  for svc in "${svcs[@]}"; do
    values="$ROOT/deploy/services/$svc.values.yaml"
    OLD[$svc]="$(grep -m1 'digest:' "$values" | sed -E 's/.*"([^"]*)".*/\1/')"
    [ "${OLD[$svc]}" = "${DIGEST[$svc]}" ] && yel "$svc: already on this digest — code unchanged"
    sed -i "s|${OLD[$svc]}|${DIGEST[$svc]}|" "$values"
  done
  if ! python3 "$ROOT/ci/check_deploy_wiring.py" >/dev/null 2>&1; then
    red "deploy-wiring guard failed — nothing shipped"
    python3 "$ROOT/ci/check_deploy_wiring.py" 2>&1 | tail -8
    for svc in "${svcs[@]}"; do   # leave the tree exactly as we found it
      sed -i "s|${DIGEST[$svc]}|${OLD[$svc]}|" "$ROOT/deploy/services/$svc.values.yaml"
    done
    rm -rf "$tmp"; return 1
  fi
  grn "pinned and guards green"

  # ── C. ship the images, in parallel ──────────────────────────────────────────────────────────
  say "3/5 ship images"
  if [ "${FAST:-0}" = "1" ]; then
    # The tunnel is opened ONCE, here, rather than raced for by every parallel push.
    open_registry_tunnel || {
      red "the node cannot reach the registry — run ./deploy/registry.sh once"
      rm -rf "$tmp"; return 1
    }
  fi
  for svc in "${svcs[@]}"; do
    (
      if [ "${FAST:-0}" = "1" ]; then
        m="$(ship_image_fast "$svc" "${DIGEST[$svc]}")" && printf '%s' "$m" > "$tmp/$svc.manifest"
      else
        docker save "raje3/$svc:ship" | "${SSH[@]}" \
          "cat > /tmp/$svc.tar && sudo -n k3s ctr images import /tmp/$svc.tar >/dev/null 2>&1 \
           && sudo -n k3s ctr images tag docker.io/raje3/$svc:ship \
              docker.io/raje3/$svc@${DIGEST[$svc]} >/dev/null 2>&1; \
           sudo -n k3s ctr images ls -q | grep -qx docker.io/raje3/$svc@${DIGEST[$svc]}" \
          && printf '%s' "${DIGEST[$svc]}" > "$tmp/$svc.manifest"
      fi
    ) &
  done
  wait

  for svc in "${svcs[@]}"; do
    if [ ! -s "$tmp/$svc.manifest" ]; then
      red "$svc: the image is NOT in containerd — the pod would ImagePullBackOff"; rc=1
    fi
  done
  [ "$rc" -eq 0 ] || { rm -rf "$tmp"; return 1; }

  # RE-PINNED TO WHAT THE REGISTRY STORES. `docker build -q` prints the CONFIG digest, and
  # containerd will happily accept a NAME containing a digest that describes nothing — which is how
  # a deployment came to be "pinned" to a number no content matched.
  if [ "${FAST:-0}" = "1" ]; then
    for svc in "${svcs[@]}"; do
      m="$(cat "$tmp/$svc.manifest")"
      values="$ROOT/deploy/services/$svc.values.yaml"
      sed -i "s|${DIGEST[$svc]}|$m|" "$values"
      sed -i "s|repository: docker.io/raje3/$svc|repository: 127.0.0.1:$REG_PORT/raje3/$svc|" "$values"
      DIGEST[$svc]="$m"
    done
    python3 "$ROOT/ci/check_deploy_wiring.py" >/dev/null 2>&1 || {
      red "deploy-wiring guard failed after re-pinning to the registry digests"
      python3 "$ROOT/ci/check_deploy_wiring.py" 2>&1 | tail -8
      rm -rf "$tmp"; return 1
    }
  fi
  grn "every image present under its digest"

  # ── D. sync every values file, then ONE rollout ──────────────────────────────────────────────
  say "4/5 sync + roll"
  local files=() list=""
  for svc in "${svcs[@]}"; do
    files+=("deploy/services/$svc.values.yaml")
    list="${list:+$list,}$svc"
  done
  if ! tar czf - -C "$ROOT" "${files[@]}" deploy/hooks deploy/server 2>/dev/null \
       | "${SSH[@]}" "cd ~/raje3 && tar xzf - 2>/dev/null && chmod +x deploy/hooks/*.sh"; then
    red "the values files did not reach the server"; rm -rf "$tmp"; return 1
  fi
  for svc in "${svcs[@]}"; do
    "${SSH[@]}" "grep -q '${DIGEST[$svc]}' ~/raje3/deploy/services/$svc.values.yaml" || {
      red "$svc: the values file on the server does not carry the new digest"; rc=1; }
  done
  [ "$rc" -eq 0 ] || { rm -rf "$tmp"; return 1; }

  "${SSH[@]}" "cd ~/raje3 && sudo -n PRODUCT_NAME=raje3 CHART=platform/deploy/chart \
     VALUES_DIR=deploy/services bash deploy/server/update.sh --only $list 2>&1 | tail -3"

  # ── E. verify each ARTIFACT, in parallel ─────────────────────────────────────────────────────
  say "5/5 verify"
  for svc in "${svcs[@]}"; do
    (
      for _ in $(seq 1 40); do
        pod="$("${SSH[@]}" "kubectl -n $NS get pods --no-headers 2>/dev/null \
          | awk '/^$svc-[0-9a-f]/ && \$3==\"Running\" && \$2==\"1/1\" {print \$1; exit}'")"
        [ -n "$pod" ] || { sleep 15; continue; }
        live="$("${SSH[@]}" "kubectl -n $NS get pod $pod \
          -o jsonpath='{.status.containerStatuses[0].imageID}'" | sed 's/.*@//')"
        [ "$live" = "${DIGEST[$svc]}" ] && { printf 'ok' > "$tmp/$svc.ok"; exit 0; }
        sleep 15
      done
      printf '%s' "${live:-no ready pod}" > "$tmp/$svc.live"
    ) &
  done
  wait

  for svc in "${svcs[@]}"; do
    if [ -f "$tmp/$svc.ok" ]; then
      grn "$svc is running the image this command built"
    else
      red "$svc: RUNNING $(cat "$tmp/$svc.live" 2>/dev/null | cut -c1-26)… but shipped ${DIGEST[$svc]:0:26}…"
      rc=1
    fi
  done
  rm -rf "$tmp"
  return "$rc"
}

if [ "$#" -eq 0 ]; then
  red "usage: [FAST=1] ./deploy/ship.sh <service> [service…]"
  exit 1
fi

if ship_many "$@"; then
  echo
  grn "shipped: $* — every one running the image this command built"
  exit 0
fi
echo
red "did not ship: $*"
exit 1
