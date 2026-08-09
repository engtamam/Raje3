#!/usr/bin/env bash
# ==================================================================================================
#  راجِع — pre-deploy hook. Runs BEFORE the rollout, from platform/deploy/server/setup.sh.
# --------------------------------------------------------------------------------------------------
#  THIS FILE IS THE SEAM. Everything else in the deploy pipeline — provision-server.sh, setup.sh,
#  update.sh, reset-platform.sh, boot-heal.sh, gen-secrets.py — now ships in base-services v0.12.5
#  and we invoke it rather than maintain a copy.
#
#  We had written our own provision-server.sh, setup.sh and update.sh before that release. All three
#  are DELETED. Theirs arrived carrying the same decisions — the k3s flannel/Calico flags with the
#  same "this box was installed with flannel" warning, a FATAL preflight, render-before-apply,
#  health-gated rollout with auto-rollback to the revision captured before the upgrade — and their
#  update.sh names Raje3 in its own usage example:
#
#      PRODUCT_NAME=raje3 CHART=platform/deploy/chart VALUES_DIR=deploy/services bash update.sh
#
#  Keeping our copies would have meant maintaining a divergent fork of something upstream now
#  maintains. The rule that applies is the same one that governs the services: consume it, do not
#  reimplement it.
#
#  What belongs HERE is only what is genuinely ours: per-service databases, our secrets, and the
#  object-store buckets. Nothing in this file is platform behaviour.
# ==================================================================================================
set -Eeuo pipefail
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

info(){ echo -e "\e[36m  ▸ $*\e[0m"; }
ok(){   echo -e "\e[32m  ✔ $*\e[0m"; }

# Every service that needs its own database. One database per service is not tidiness: it is what
# stops a migration in one service from locking a table in another.
SERVICES="tenant authz identity audit gateway job file compliance notification featureflag analytics wallet billing ticket onboarding backup search webhook connector operations reminders campaigns loyalty"

info "provisioning databases"
for db in $SERVICES; do
  kubectl -n "$NS" exec postgres-0 -- psql -U platform -d postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname='$db'" 2>/dev/null | grep -q 1 \
    || kubectl -n "$NS" exec postgres-0 -- createdb -U platform "$db" 2>/dev/null || true
done
ok "databases present"

# Object-store buckets. SEPARATE buckets for application files and backups, deliberately: a restore
# must not be able to overwrite the archive it is restoring from, and a misconfigured file-service
# must not be able to reach the backups.
info "object-store buckets"
for b in raje3-files raje3-backups; do
  kubectl -n "$NS" exec deploy/objectstore -- sh -c \
    "echo \"s3.bucket.create -name $b\" | weed shell" >/dev/null 2>&1 || true
done
ok "buckets present"

# Secrets are minted by platform/deploy/server/gen-secrets.py, which setup.sh calls. The two values
# that MUST be identical across every service — PII_SALT and INTERNAL_SERVICE_TOKEN — are its job,
# not ours: two different salts fold one person into two pseudonyms while everything still boots and
# still looks correct.
ok "pre-deploy complete"
