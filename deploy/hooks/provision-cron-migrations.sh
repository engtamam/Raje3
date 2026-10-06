#!/usr/bin/env bash
# ==================================================================================================
#  EVERY SERVICE'S CronJob -> job-service PUSH DISPATCH, IN ONE PASS, ACTIVE FROM A FRESH INSTALL
# --------------------------------------------------------------------------------------------------
#  WHY THIS EXISTS. Seven services (whatsapp-assistant, insights, reminders, campaigns,
#  affiliate-service, loyalty, operations — 2026-09-16, all ~25 of our own cron entries) had their
#  `cronJobs:` chart block removed and replaced with a job-service schedule + push-dispatch target,
#  documented as a comment in each service's own values.yaml. Documentation the installer never
#  runs is a fresh install that ships with every one of those services INERT — every probe green,
#  nothing ever fires — the exact playbook trap §4.1 the CronJobs themselves existed to avoid.
#
#  THIS SCRIPT IS THAT MISSING CALLER — one entry per route below, each a
#  (schedule name, cron, queue, job type, service:port, internal path) tuple copied VERBATIM from
#  its own service's values.yaml comment (the single source of truth; keep the two in step by hand
#  if a schedule ever changes). Runs deploy/hooks/job-schedule.sh create (idempotent by name — see
#  that script's own header) then job-dispatch-target.sh register (idempotent by queue) for each,
#  so a re-run on every install/reinstall is always safe and changes nothing once already
#  provisioned.
#
#  REQUIRES deploy/hooks/provision-job-service-automation.sh TO HAVE RUN FIRST (the credential
#  job-schedule.sh mints its bearer from) — bring-up.sh already orders it that way.
#
#  USAGE
#    bash deploy/hooks/provision-cron-migrations.sh
# ==================================================================================================
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

C_G=$'\e[32m'; C_R=$'\e[31m'; C_C=$'\e[36m'; C_N=$'\e[0m'
ok(){  echo -e "${C_G}  ✔ $*${C_N}"; }
red(){ echo -e "${C_R}  ✘ $*${C_N}" >&2; }
info(){ echo -e "${C_C}  ▸ $*${C_N}"; }

# name|cron|queue|type|host:port|internal_path — one row per route, in the exact order each
# service's own values.yaml comment lists them.
ROUTES=(
  "whatsapp-tick|* * * * *|whatsapp-tick|whatsapp.tick|whatsapp-assistant:8000|/internal/whatsapp_assistant/tick"

  "insights-tick|0 1,4,7,10,13,16,19,22 * * *|insights-tick|insights.tick|insights:8000|/internal/insights/tick"
  "insights-platform-rollup|20 1,4,7,10,13,16,19,22 * * *|insights-platform-rollup|insights.platform_rollup|insights:8000|/internal/insights/platform-rollup"

  "reminders-tick|4-59/5 * * * *|reminders-tick|reminders.tick|reminders:8000|/internal/reminders/tick"
  "reminders-receipts|3,13,23,33,43,53 * * * *|reminders-receipts|reminders.receipts_pull|reminders:8000|/internal/reminders/receipts/pull"

  "campaigns-tick|*/15 * * * *|campaigns-tick|campaigns.tick|campaigns:8000|/internal/campaigns/tick"
  "campaigns-jobs-run|* * * * *|campaigns-jobs-run|campaigns.jobs_run|campaigns:8000|/internal/campaigns/jobs/run"

  "commissions-sweep|17 * * * *|commissions-sweep|affiliate.commissions_sweep|affiliate-service:8000|/internal/commissions/sweep"
  "leads-tick|* * * * *|leads-tick|affiliate.leads_tick|affiliate-service:8000|/internal/leads/tick"
  "tickets-escalation-sweep|*/15 * * * *|tickets-escalation-sweep|affiliate.tickets_escalation_sweep|affiliate-service:8000|/internal/tickets/escalation-sweep"

  "loyalty-tick|10 3 * * *|loyalty-tick|loyalty.tick|loyalty:8000|/internal/loyalty/tick"
  "loyalty-recover|*/15 * * * *|loyalty-recover|loyalty.recover|loyalty:8000|/internal/loyalty/recover"
  "loyalty-replay-free-visits|25 * * * *|loyalty-replay-free-visits|loyalty.replay_free_visits|loyalty:8000|/internal/loyalty/replay-free-visits"

  "retention-sweep|17 1 * * *|retention-sweep|operations.retention_sweep|operations:8000|/internal/operations/retention/sweep"
  "wallet-topups-reconcile|3-59/5 * * * *|wallet-topups-reconcile|operations.wallet_topups_reconcile|operations:8000|/internal/operations/wallet-topups/reconcile"
  "gauges-reconcile|41 2 * * *|gauges-reconcile|operations.gauges_reconcile|operations:8000|/internal/operations/gauges/reconcile"
  "partner-statements|40 3 2 * *|partner-statements|operations.partner_statements|operations:8000|/internal/operations/partners/statements/run"
  "visit-reseam|6/10 * * * *|visit-reseam|operations.visit_reseam|operations:8000|/internal/operations/visits/reseam"
  "whatsapp-health|53 * * * *|whatsapp-health|operations.whatsapp_health|operations:8000|/internal/operations/whatsapp/health"
  "template-approvals|23 * * * *|template-approvals|operations.template_approvals|operations:8000|/internal/operations/templates/sync-approvals"
  "template-publish|47 * * * *|template-publish|operations.template_publish|operations:8000|/internal/operations/templates/publish"
  "salla-refresh-scan|14 4 * * *|salla-refresh-scan|operations.salla_refresh_scan|operations:8000|/internal/operations/salla/refresh-scan"
  "salla-jobs-run|2-59/5 * * * *|salla-jobs-run|operations.salla_jobs_run|operations:8000|/internal/operations/salla/jobs/run"
  "renewal-heads-up-scan|26 4 * * *|renewal-heads-up-scan|operations.renewal_heads_up_scan|operations:8000|/internal/operations/subscriptions/renewal-heads-up/scan"
  "renewal-heads-up-jobs-run|4-59/5 * * * *|renewal-heads-up-jobs-run|operations.renewal_heads_up_jobs_run|operations:8000|/internal/operations/subscriptions/renewal-heads-up/jobs/run"
  "translations-scan|*/10 * * * *|translations-scan|operations.translations_scan|operations:8000|/internal/operations/translations/scan"
  "translations-jobs-run|*/2 * * * *|translations-jobs-run|operations.translations_jobs_run|operations:8000|/internal/operations/translations/jobs/run"

  "coworking-memberships-renew|0 * * * *|coworking-memberships-renew|coworking.memberships_renew|coworking:8000|/internal/coworking/memberships/renew"
)

FAILED=0
for row in "${ROUTES[@]}"; do
  IFS='|' read -r name cron queue type host_port path <<< "$row"
  info "$name"
  if ! bash "$HERE/job-schedule.sh" create "$name" "$cron" "$queue" "$type"; then
    red "$name: schedule creation failed"; FAILED=1; continue
  fi
  if ! bash "$HERE/job-dispatch-target.sh" register "$queue" "http://$host_port$path"; then
    red "$name: dispatch target registration failed"; FAILED=1; continue
  fi
done

if [ "$FAILED" -eq 0 ]; then
  ok "all ${#ROUTES[@]} routes provisioned (or already were)"
else
  red "one or more routes failed — see above"
  exit 1
fi
