#!/usr/bin/env bash
# Re-mirrors bitnami/kubectl's current `latest` into our own GHCR, pinned by digest, and prints
# the line to paste into deploy/k3s/pod-reaper.yaml's own `image:` field.
#
# WHY THIS EXISTS. bitnami/kubectl started returning "not found" for every versioned tag we had
# pinned (2026-09-29) — Bitnami dropped its free-tier version history and now publishes only a
# moving `latest`. Depending on someone else's tag lifecycle for a self-healing watchdog is the
# exact unpinned-dependency risk this repo refuses everywhere else (every service image here is
# published by digest, never `:latest`). This script applies that same discipline to a base image
# we did not build: pull the current `latest` once, push it into our own registry under an
# immutable digest, and point pod-reaper at OUR copy — Bitnami can no longer take it away.
#
# Run this again only if the mirrored digest is ever retired from our own GHCR (it will not be,
# short of us deleting it) or a newer kubectl is genuinely wanted.
set -euo pipefail

GHCR_USER="${GHCR_USER:?set GHCR_USER}"
GHCR_TOKEN="${GHCR_TOKEN:?set GHCR_TOKEN}"
DEST="ghcr.io/${GHCR_USER}/raje3/pod-reaper-kubectl"
TAG="mirror-$(date +%Y-%m-%d)"

echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin

docker pull bitnami/kubectl:latest
SRC_DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' bitnami/kubectl:latest | cut -d@ -f2)"

docker tag "bitnami/kubectl@${SRC_DIGEST}" "${DEST}:${TAG}"
docker push "${DEST}:${TAG}"

DEST_DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' "${DEST}:${TAG}" | cut -d@ -f2)"

echo
echo "Paste this into deploy/k3s/pod-reaper.yaml's own \`image:\` field:"
echo "  image: ${DEST}@${DEST_DIGEST}"
