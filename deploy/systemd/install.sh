#!/usr/bin/env bash
# ==================================================================================================
#  install.sh — register the boot units, once.
# --------------------------------------------------------------------------------------------------
#  Run from the repo on the server:  sudo bash deploy/systemd/install.sh
#
#  IT IS SAFE TO RUN AGAIN. Copies, reloads, enables — all idempotent — so this is part of an
#  install rather than a thing somebody has to remember not to repeat.
# ==================================================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

C_G=$'\e[32m'; C_D=$'\e[2m'; C_N=$'\e[0m'

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 2; }

# THE UNITS NAME AN ABSOLUTE PATH, so a repo checked out somewhere else needs them rewritten rather
# than copied. Doing that here beats a README line that says "edit the file first".
for unit in raje3-up.service raje3-gateway-forward.service; do
  sed "s#/home/deploy/raje3#$ROOT#g" "$HERE/$unit" > "/etc/systemd/system/$unit"
done
chmod +x "$HERE/on-boot.sh"

systemctl daemon-reload
systemctl enable raje3-up.service raje3-gateway-forward.service >/dev/null

echo "${C_G}✔ raje3-up and raje3-gateway-forward will start with the machine${C_N}"
echo "  ${C_D}root: $ROOT${C_N}"
echo "  ${C_D}check after a reboot: systemctl status raje3-up${C_N}"
