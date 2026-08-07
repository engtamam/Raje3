#!/usr/bin/env bash
# =============================================================================
# setup.sh — prepare a fresh clone of the Raje3 repo.
#
# The platform/ submodule is base-services (dozens of services + docs + chart).
# We only ever use its Helm CHART and its CI HARNESS — never the service source,
# which we run from published images. So we sparse-checkout just those two paths:
# a fraction of the size on disk, the full version pin kept in git.
#
#   deploy/     the chart, per-service values, k3s bootstrap + preflight
#   tools/ci/   run_all_gates.sh + gate library (our ci:harness-sync compares to these)
#
# Nothing is copied and nothing is edited. The submodule stays pinned to its tag.
# To read a platform service's source temporarily (e.g. to learn its config knobs):
#   git -C platform sparse-checkout disable      # reveal source
#   git -C platform sparse-checkout reapply       # hide it again
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

C_G=$'\e[32m'; C_C=$'\e[36m'; C_N=$'\e[0m'
info(){ echo -e "${C_C}▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }

info "init the platform submodule (pinned)"
git submodule update --init platform

info "sparse-checkout: chart + CI harness only (not the service source)"
git -C platform sparse-checkout init --cone
git -C platform sparse-checkout set deploy tools/ci

ok "platform/ on disk: $(du -sh platform 2>/dev/null | cut -f1 || echo '?')  (source excluded)"
ok "pinned at: $(git -C platform describe --tags 2>/dev/null || git -C platform rev-parse --short HEAD)"
echo
ok "ready — validate identity with:  python3 ci/check_product_config.py"
