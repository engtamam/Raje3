#!/usr/bin/env bash
# Stand up the image registry — run ONCE, then use `FAST=1 ./deploy/ship.sh <svc>`.
#
# WHY. `docker save | ssh` moves the WHOLE image on every ship: ninety megabytes over an SSH tunnel
# because one Python file changed. The interpreter, the OS packages and the dependencies are byte
# for byte what the node already has, and they travel again anyway — a tarball cannot know what the
# other end is holding.
#
# A registry can. `docker push` sends only the layers that are missing, and our Dockerfiles copy the
# source LAST, so a code edit rebuilds exactly one small layer.
#
# THE REGISTRY RUNS HERE, NOT ON THE NODE, AND THAT IS THE WHOLE TRICK.
#
# The obvious arrangement — registry on the node, push to it through a forward — cannot work with
# Docker Desktop, and it cost an hour to see why: the daemon lives in its own Linux VM, so the
# `127.0.0.1` it dials is that VM's loopback and not the Windows host's. Every push died on
# "connection refused" against a port `curl` could reach from the same shell.
#
# So it is turned around. The registry sits next to the daemon, where a push is local and instant,
# and the NODE reaches it through a REVERSE forward (`ssh -R`) when containerd pulls. Only the
# missing layers cross the wire, in the direction that has to carry them anyway.
#
# PLAIN HTTP ON LOOPBACK, AND THAT IS NOT A SHORTCUT THAT WEAKENS ANYTHING. It listens on
# 127.0.0.1 only, on the developer's own machine, and the SSH tunnel is what carries the pull. TLS
# on a loopback socket protects against an attacker who is already inside the laptop.
#
# NOT A PRODUCTION ARTEFACT STORE. It holds development builds. The pin still travels in the values
# file, and ship.sh still verifies the running pod's imageID against the digest it built — the
# registry changes the road, not the rule.
set -uo pipefail

REMOTE="${REMOTE:-tamam@127.0.0.1}"
PORT="${PORT:-2224}"
# 5055 AND NOT 5000, WHICH IS THE OBVIOUS CHOICE AND THE WRONG ONE HERE. VirtualBox publishes
# forwards on 127.0.0.1:5000, so the socket cannot be bound — the same collision cost an afternoon
# on 8080 earlier the same night.
REG_PORT="${REG_PORT:-5055}"
SSH=(ssh -o BatchMode=yes -p "$PORT" "$REMOTE")

red(){ printf '\e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '\e[32m✔ %s\e[0m\n' "$*"; }
say(){ printf '\n\e[1m▸ %s\e[0m\n' "$*"; }

say "1/3 the registry, beside the daemon that pushes to it"
# RESTART=always, because a laptop that reboots must not come back without the thing every ship
# needs — a missing registry fails the NEXT ship with an error nobody connects to a reboot.
if ! docker inspect raje3-registry >/dev/null 2>&1; then
  docker run -d --restart=always --name raje3-registry \
    -p "127.0.0.1:$REG_PORT:5000" -v raje3-registry-data:/var/lib/registry registry:2 >/dev/null \
    || { red "could not start the registry"; exit 1; }
fi
for _ in $(seq 1 20); do
  curl -fsS -m 3 -o /dev/null "http://127.0.0.1:$REG_PORT/v2/" 2>/dev/null && break
  sleep 1
done
curl -fsS -m 3 -o /dev/null "http://127.0.0.1:$REG_PORT/v2/" 2>/dev/null \
  || { red "the registry is not answering on 127.0.0.1:$REG_PORT"; exit 1; }
grn "registry answering on 127.0.0.1:$REG_PORT"

say "2/3 teach the node's containerd where it will be"
# THE KEY IS THE HOST IN THE IMAGE REF, LITERALLY. containerd on the node dials its OWN 127.0.0.1,
# which the reverse forward ship.sh opens carries back to the registry on this machine.
#
# `insecure_skip_verify` because the registry speaks plain HTTP — see the header.
if ! "${SSH[@]}" "sudo -n mkdir -p /etc/rancher/k3s && \
  printf 'mirrors:\n  \"127.0.0.1:$REG_PORT\":\n    endpoint:\n      - \"http://127.0.0.1:$REG_PORT\"\nconfigs:\n  \"127.0.0.1:$REG_PORT\":\n    tls:\n      insecure_skip_verify: true\n' \
    | sudo -n tee /etc/rancher/k3s/registries.yaml >/dev/null && \
  grep -q '$REG_PORT' /etc/rancher/k3s/registries.yaml"; then
  red "could not write registries.yaml on the node"; exit 1
fi
grn "containerd points at it"

say "3/3 restart k3s so it reads the file"
# ONLY IF THE FILE CHANGED WHAT IT SAYS. k3s reads registries.yaml at start, and a restart on a
# loaded single-node cluster is minutes of DNS flapping — it took CoreDNS down for a quarter of an
# hour once already tonight, and every rollout that overlapped it failed for unrelated reasons.
"${SSH[@]}" "sudo -n systemctl restart k3s" || { red "k3s restart failed"; exit 1; }
for _ in $(seq 1 60); do
  if "${SSH[@]}" "kubectl get nodes --no-headers 2>/dev/null | grep -q ' Ready '"; then
    grn "node Ready — ship with: FAST=1 ./deploy/ship.sh <service>"
    exit 0
  fi
  sleep 5
done
red "the node did not return Ready after 300s — check 'systemctl status k3s' on the box"
exit 1
