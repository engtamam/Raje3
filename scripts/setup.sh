#!/usr/bin/env bash
# =============================================================================
# setup.sh — prepare a fresh clone of the Raje3 repo.
#
# The platform/ submodule is base-services: two dozen services, the Helm chart, the CI harness.
# WE CHECK OUT ALL OF IT, and that is a deliberate reversal of what this script used to do.
#
# It used to sparse-checkout deploy/ and tools/ci only, on the reasoning that we run services from
# published images and never need their source. That reasoning is wrong twice over:
#
#   * Our own guard reads it. ci/check_deploy_wiring.py answers questions no values file can —
#     does this service actually SERVE the route a CronJob is scheduled against, is this env key a
#     field its Settings declares, does it implement the erasure contract. Without the source those
#     checks silently degrade to "unchecked", which is the worst state for a guard: green and blind.
#
#   * It is how we work. Every service is read in full — manifest, routes, config, ports — before a
#     single line of its values file is written. Every real finding this project has produced came
#     from reading source, not documentation: the tenant claim is `tenant` and not `tenant_id`; the
#     WhatsApp inbound verifier wants a timestamp Meta does not send; the postgres pool is opened
#     with no arguments. None of that is visible from deploy/.
#
# The whole submodule is ~38MB of text and its history ~11MB. That is a rounding error next to the
# gigabytes of images the same platform ships, and a very cheap price for reading what we deploy.
#
# Nothing here is ever edited. platform/ is read-only; a missing capability is reported upstream.
# ===========================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

C_G=$'\e[32m'; C_C=$'\e[36m'; C_N=$'\e[0m'
info(){ echo -e "${C_C}▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }

info "init the platform submodule (pinned)"
git submodule update --init platform

info "full checkout — our guards read the service source, and so do we"
git -C platform sparse-checkout disable 2>/dev/null || true

ok "platform/ on disk: $(du -sh platform 2>/dev/null | cut -f1 || echo '?')"
ok "pinned at: $(git -C platform describe --tags 2>/dev/null || git -C platform rev-parse --short HEAD)"
echo
ok "ready. Validate before deploying anything:"
echo "     python3 ci/check_product_config.py     # the product identity is intact"
echo "     python3 ci/check_deploy_wiring.py      # digests, databases, erasure, cron, env, egress"
