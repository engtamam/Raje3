#!/usr/bin/env bash
# ==================================================================================================
#  install.sh — THE ONE COMMAND on the server.  sudo bash deploy/install.sh
# --------------------------------------------------------------------------------------------------
#  It asks for what it cannot know, ONCE, at the top — then runs to the end without stopping to
#  ask anything else. A script that interrupts a twenty-minute install at minute fourteen for a
#  domain name is a script somebody walks away from and returns to find waiting.
#
#  FOUR RULES, AND EACH ONE IS A FAILURE WE HAVE ALREADY LIVED:
#
#    1. IT READS FROM /dev/tty, NOT stdin.  `curl … | bash` and `bash install.sh < /dev/null` both
#       leave stdin unusable; a prompt on stdin then reads EOF, takes an empty answer as an answer,
#       and installs a platform with no domain and no admin.
#
#    2. AN ENVIRONMENT VARIABLE SKIPS ITS QUESTION.  `DOMAIN=… sudo bash deploy/install.sh` asks
#       nothing, so the same file serves a person and a pipeline. Automation must never hang on a
#       question nobody is there to answer.
#
#    3. SECRETS ARE READ HIDDEN AND NEVER WRITTEN TO DISK.  They go straight into cluster secrets.
#       The answers that are NOT secret are remembered in a root-only file, so a re-run offers them
#       back and you press Enter — a second run must not be a second interrogation.
#
#    4. ONE INSTALL AT A TIME.  A lock, because two of these racing on one cluster is not a
#       theoretical concern: it happened today, one wiped the namespace under the other, and the
#       wreckage read exactly like a product defect.
#
#  Env that skips a prompt: DOMAIN · ACME_EMAIL · ADMIN_EMAIL · ADMIN_PASSWORD · GHCR_USER ·
#                           GHCR_TOKEN · WIPE=1 (destructive) · ASSUME_YES=1
# ==================================================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
NS="${NS:-base-services}"
CONF="/etc/raje3/install.conf"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_B=$'\e[1m'; C_D=$'\e[2m'; C_N=$'\e[0m'
phase(){ echo -e "\n${C_B}${C_C}══════ $* ══════${C_N}"; }
ok(){    echo -e "${C_G}✔ $*${C_N}"; }
WARNED=0
warn(){  WARNED=$((WARNED+1)); echo -e "${C_Y}⚠ $*${C_N}"; }
die(){   echo -e "${C_R}✖ $*${C_N}" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "run as root: sudo bash $0"

# ── the lock ──────────────────────────────────────────────────────────────────────────────────
# NON-BLOCKING, AND IT SAYS WHY. Waiting silently behind another install looks identical to a
# hang; refusing with a sentence sends the reader to the terminal that is already running one.
exec 9>/var/lock/raje3-install.lock || die "cannot open the install lock"
if ! flock -n 9; then
  die "another install is running on this machine (lock: /var/lock/raje3-install.lock).
     Two of these on one cluster wipe each other's work — wait for it, or check: pgrep -fa install.sh"
fi

# ── what is on this box ───────────────────────────────────────────────────────────────────────
echo -e "${C_B}راجِع — install${C_N}"
[ -f "$ROOT/VERSION" ] && sed 's/^/  /' "$ROOT/VERSION"

# ── 0 · the questions, all of them, now ───────────────────────────────────────────────────────
mkdir -p "$(dirname "$CONF")"; chmod 700 "$(dirname "$CONF")"
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

# EXISTENCE IS NOT USABILITY. /dev/tty is a file on every Linux box; under `ssh host 'cmd'` there
# is no controlling terminal behind it, so opening it fails and `[ -e ]` still says yes — which is
# how a non-interactive run printed «No such device or address» twice and then carried on. Open it.
_tty(){ { : </dev/tty; } 2>/dev/null; }
_ask(){  # <prompt> <default>
  local p="$1" d="${2:-}" v=""
  if ! _tty; then printf '%s' "$d"; return; fi
  if [ -n "$d" ]; then read -r -p "$p [$d]: " v </dev/tty || true; else read -r -p "$p: " v </dev/tty || true; fi
  printf '%s' "${v:-$d}"
}
_asks(){ # hidden
  local p="$1" v=""
  if ! _tty; then printf ''; return; fi
  read -rs -p "$p: " v </dev/tty || true; echo >/dev/tty; printf '%s' "$v"
}

phase "0 · what only you know"
[ -z "${DOMAIN:-}" ]      && DOMAIN="$(_ask 'النطاق (مثال kobo-cloud.com) — اتركه فارغاً لتثبيت محلي' "${DOMAIN_SAVED:-}")"
[ -z "${ACME_EMAIL:-}" ]  && ACME_EMAIL="$(_ask 'بريد شهادات TLS' "${ACME_EMAIL_SAVED:-admin@${DOMAIN:-localhost}}")"
[ -z "${ADMIN_EMAIL:-}" ] && ADMIN_EMAIL="$(_ask 'بريد حساب الإدارة (حسابنا نحن)' "${ADMIN_EMAIL_SAVED:-}")"

# THE PASSWORD IS GENERATED WHEN LEFT BLANK, AND SHOWN ONCE.
# A weak one here is not a small risk: this account can connect a WhatsApp number and message
# people in an establishment's name, and it sits behind a hostname that is in public DNS within
# minutes of the install. The policy floor is 12 characters and is enforced by identity itself —
# so a short answer would be rejected LATER, halfway through, which is the worst possible moment.
if [ -z "${ADMIN_PASSWORD:-}" ]; then
  ADMIN_PASSWORD="$(_asks 'كلمة مرور الإدارة (12 حرفاً فأكثر — اتركها فارغة لتوليدها)')"
  if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
    GENERATED=1
  fi
fi
if [ "${#ADMIN_PASSWORD}" -lt 12 ]; then
  die "كلمة المرور أقصر من 12 حرفاً — وهو حدٌّ تفرضه الهوية نفسها، فالرفض سيأتي في منتصف التثبيت لا هنا."
fi

# THE REGISTRY. The images are private; without this the rollout pulls nothing and every pod sits
# in ImagePullBackOff — a failure that reads like a broken cluster and is a missing password.
[ -z "${GHCR_USER:-}" ]  && GHCR_USER="$(_ask 'مستخدم ghcr.io' "${GHCR_USER_SAVED:-}")"
[ -z "${GHCR_TOKEN:-}" ] && GHCR_TOKEN="$(_asks 'رمز ghcr.io (read:packages) — مخفي')"

[ -n "${ADMIN_EMAIL:-}" ] || warn "بلا حساب إدارة — يمكن إنشاؤه لاحقاً"
[ -n "${GHCR_TOKEN:-}" ]  || warn "بلا رمز صور — السحب سيفشل إن كانت الصور خاصة"

# REMEMBERED: everything except the secrets. Root-only, and it is why the second run is three
# presses of Enter instead of the same five questions.
cat > "$CONF" <<CONFEOF
# راجِع — answers kept so a re-run does not ask again. NO SECRETS ARE STORED HERE.
DOMAIN_SAVED="${DOMAIN:-}"
ACME_EMAIL_SAVED="${ACME_EMAIL:-}"
ADMIN_EMAIL_SAVED="${ADMIN_EMAIL:-}"
GHCR_USER_SAVED="${GHCR_USER:-}"
CONFEOF
chmod 600 "$CONF"

echo
echo -e "  النطاق        ${C_B}${DOMAIN:-—(محلي)}${C_N}"
echo -e "  شهادات        ${C_B}${ACME_EMAIL}${C_N}"
echo -e "  حساب الإدارة  ${C_B}${ADMIN_EMAIL:-—}${C_N}"
echo -e "  الصور         ${C_B}${GHCR_USER:-—}${C_N} ${C_D}(الرمز لا يُعرض ولا يُحفظ)${C_N}"
if [ "${ASSUME_YES:-0}" != "1" ] && _tty; then
  read -r -p "ابدأ التثبيت؟ [y/N]: " go </dev/tty || true
  case "${go:-}" in y|Y|yes|نعم) ;; *) die "أُلغي — لم يُمسّ شيء";; esac
fi

export DOMAIN ACME_EMAIL ADMIN_EMAIL ADMIN_PASSWORD GHCR_USER GHCR_TOKEN

# ── 1 · the registry credential, before k3s starts ────────────────────────────────────────────
# ONLY THE FILE HERE — the cluster-side secret is minted by bring-up.sh, in the first second a
# cluster exists. This ran kubectl on a virgin host once and printed `command not found` three
# times before the real failure; on a machine installed earlier it had looked fine for weeks.
phase "1 · اعتماد الصور"
if [ -n "${GHCR_TOKEN:-}" ]; then
  # WHERE THE KUBELET LOOKS. k3s reads /etc/rancher/k3s/registries.yaml for pulls that happen
  # outside a pod spec — the pre-pull our rollout does, for one — and it reads it AT START, so
  # writing it before k3s is installed is not merely allowed, it is the right moment.
  install -d -m 700 /etc/rancher/k3s
  # MERGED, NOT WRITTEN OVER. This file has a second author — `registry.sh` writes the node-local
  # mirror the fast ship path pulls from — and both used to `cat >` the whole thing, so whichever
  # ran last silently erased the other and restarted k3s on top of it. Losing the credential means
  # ImagePullBackOff on all eighteen private platform images, reading like a broken registry
  # rather than a file that was overwritten; losing the mirror breaks every fast ship. (ل-5)
  . "$(dirname "$0")/lib/registries.sh"
  registries_merge /etc/rancher/k3s/registries.yaml configs <<REGEOF
configs:
  "ghcr.io":
    auth:
      username: "${GHCR_USER:-x}"
      password: "${GHCR_TOKEN}"
REGEOF
  chmod 600 /etc/rancher/k3s/registries.yaml
  ok "اعتماد ghcr مكتوب حيث يقرأه kubelet"
  # ONLY IF IT IS ALREADY RUNNING. On a first install there is no k3s to restart, and a restart of
  # a unit that does not exist is a red line of output that frightens the reader for nothing.
  systemctl is-active --quiet k3s && systemctl restart k3s >/dev/null 2>&1 || true
else
  warn "بلا رمز — تخطّي اعتماد الصور"
fi

# ── 2 · the platform ──────────────────────────────────────────────────────────────────────────
phase "2 · المنصة"
if [ "${WIPE:-0}" = "1" ]; then
  bash "$HERE/bring-up.sh" --wipe || die "التثبيت فشل — راجع السطر أعلاه"
else
  bash "$HERE/bring-up.sh" || die "التثبيت فشل — راجع السطر أعلاه"
fi

# ── 3 · the boot units ────────────────────────────────────────────────────────────────────────
phase "3 · الإقلاع"
bash "$HERE/systemd/install.sh" || warn "لم تُسجَّل وحدات الإقلاع"

# ── 4 · THE LAST QUESTION, ASKED BY THE INSTALLER ITSELF ──────────────────────────────────────
# «هل يفتح النطاق؟» is the only question the owner will ask, and until today nothing in this script
# asked it. Every layer reported success — 24 services ready, a certificate issued, an edge applied
# — while the site was dark, because a liveness probe was killing the one pod that owns 443 every
# thirty-five seconds. Twenty-four green lines and a domain that refused connections.
#
# So the install ends by being a visitor: a real request over the public name, from this machine.
# Nothing below is inferred from cluster state — a pod can be Running and answer nothing.
phase "الفحص الأخير"
if [ -n "${DOMAIN:-}" ]; then
  EDGE_OK=0
  for _ in $(seq 1 30); do
    code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://${DOMAIN}/" 2>/dev/null || true)"
    case "$code" in 200|301|302|308) EDGE_OK=1; break;; esac
    sleep 5
  done
  if [ "$EDGE_OK" = "1" ]; then
    # AND THE CERTIFICATE SEPARATELY, because a page served over a self-signed or expired cert is a
    # browser warning, which for a shop owner is the same as being down.
    if curl -s -o /dev/null --max-time 15 "https://${DOMAIN}/" 2>/dev/null; then
      ok "https://${DOMAIN} يجيب، وشهادته صالحة"
    else
      warn "الموقع يجيب لكن الشهادة غير موثوقة بعد — قد تحتاج ACME دقائق"
    fi
  else
    warn "https://${DOMAIN} لا يجيب — الخدمات جاهزة لكن الحافة لا تخدم:
       kubectl -n $NS get pods -l app=edge
       kubectl -n $NS logs -l app=edge --tail=30"
  fi
fi

# ── 5 · what to do next, and the one thing shown only once ────────────────────────────────────
phase "تم"
[ "$WARNED" -eq 0 ] && ok "اكتمل التثبيت" || warn "اكتمل التثبيت مع $WARNED تحذيراً"
if [ -n "${GENERATED:-}" ]; then
  echo
  echo -e "${C_B}  كلمة مرور الإدارة (تُعرض مرة واحدة فقط):${C_N}  ${ADMIN_PASSWORD}"
  echo -e "${C_D}  احفظها الآن — لا تُخزَّن في أي ملف، وتغييرها من «حسابي».${C_N}"
fi
[ -n "${DOMAIN:-}" ] && echo -e "${C_D}  اللوحة: https://${DOMAIN}   ·   العميل: https://my.${DOMAIN}   ·   البوابة: https://api.${DOMAIN}${C_N}"
