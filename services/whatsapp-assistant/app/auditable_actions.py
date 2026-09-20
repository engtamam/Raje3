"""whatsapp-assistant — auditable actions: what this service must be able to PROVE it did.

See services/loyalty/app/auditable_actions.py for the full house-style explanation of this file's
format and the four action sources. `whatsapp_assistant.booking_confirmed` is the ONE state-
changing tool this service can ever fire on a customer's behalf (app/core/tools.py), reached only
from a button_reply match, never from the model's own decision — a reward the customer attaches to
that booking rides along as `intended_reward_id` INTENT, never a separate spend of its own (see
app/core/booking_assignment.py's own note): there used to be a second one here,
`whatsapp_assistant.points_redeemed`, for the standalone unconditional-on-confirm redemption
`suggest_redeemable_offer` used to trigger directly — removed along with that code path, not left
behind as a declared-but-uncalled action.
"""
from __future__ import annotations

from typing import Any

AUDITABLE_ACTIONS: list[dict[str, Any]] = [
    {
        "action": "whatsapp_assistant.booking_confirmed",
        "source": "internal",
        "critical": True,
        "resource": "booking",
        "why": "a booking made on a customer's behalf with nobody standing at a counter to "
               "witness it. If the audit log cannot record it, the action must not happen — an "
               "unprovable auto-booking is indistinguishable from a bug that double-booked a slot",
    },
    {
        "action": "whatsapp_assistant.booking_cancelled",
        "source": "internal",
        "critical": True,
        "resource": "booking",
        "why": "a booking cancelled on a customer's behalf via the button-confirm gate — same "
               "reasoning as booking_confirmed above: an unprovable auto-cancel is indistinguishable "
               "from a bug that dropped a customer's appointment, and the shop needs to be able to "
               "show WHY a slot that looked booked opened back up",
    },
    {
        "action": "whatsapp_assistant.booking_rescheduled",
        "source": "internal",
        "critical": True,
        "resource": "booking",
        "why": "a booking's time moved on a customer's behalf via the button-confirm gate — same "
               "reasoning as booking_confirmed/booking_cancelled above: an unprovable auto-move is "
               "indistinguishable from a bug that silently relocated an appointment",
    },
    {
        "action": "whatsapp_assistant.chat_retention_purged",
        "source": "internal",
        "critical": True,
        "resource": "conversation",
        "why": "a bulk, irreversible delete of a customer's raw chat content past "
               "CHAT_RETENTION_DAYS (app/core/retention.py). Critical for the same reason "
               "erasure is: once the content is gone there is nothing left to show a purge "
               "happened at all, or that it happened for the reason (age, not something else) "
               "the retention policy claims — an unprovable bulk delete of chat history is "
               "indistinguishable from a bug that ate a shop's conversations",
    },
    {
        "action": "subject.erased",
        "source": "system",
        "critical": True,
        "resource": "subject",
        "why": "this service's leg of a DSAR fan-out (app/core/erasure.py) — same action name as "
               "every other service's leg (see services/reminders/app/auditable_actions.py), so "
               "compliance-service's fan-out can be shown to have completed everywhere rather "
               "than assumed. Erasure is irreversible; without a record we cannot prove we "
               "honoured the request, and the data itself is gone so nothing else can show it",
    },
    {
        "action": "whatsapp_assistant.escalated_to_human",
        "source": "internal",
        "critical": True,
        "resource": "conversation",
        "why": "the AI stopped replying and handed a customer off to a human (mandatory triage "
               "complaint pick, the frustration heuristic, or a direct mid-conversation request) "
               "— the shop's own staff already see the same WhatsApp thread via Meta coexistence, "
               "so nothing further is sent anywhere else. If this cannot be recorded there is no "
               "way to prove the handoff happened or why — which matters most exactly when a "
               "customer later says nobody ever got back to them",
    },
    {
        "action": "whatsapp_assistant.stopped_wallet_depleted",
        "source": "internal",
        "critical": True,
        "resource": "conversation",
        "why": "the AI stopped replying to a customer because the shop's wallet has no funds "
               "beyond its plan's included quota — a real operational stop, not a human "
               "escalation (it is true for every customer of this shop at once, not about how "
               "this one conversation went). If this cannot be recorded there is no way to later "
               "show a shop owner exactly when and why their customers stopped getting answers",
    },
    {
        "action": "whatsapp_assistant.stopped_not_subscribed",
        "source": "internal",
        "critical": True,
        "resource": "conversation",
        "why": "the AI stopped replying because this shop does not hold `feature.whatsapp` — never "
               "bought it, or the subscription lapsed. A real operational stop, same shape as "
               "stopped_wallet_depleted above (true for every customer of this shop, not this one "
               "conversation). If this cannot be recorded there is no way to later show a shop "
               "owner exactly when their customers stopped getting AI replies and why",
    },
    {
        "action": "whatsapp_assistant.proposal_rejected",
        "source": "system",
        "critical": False,
        "resource": "proposal",
        "why": "the server-side re-validation gate (core/tools.py) refused a model's proposal — "
               "a slot that filled, a reward that no longer qualifies. Not critical: refusing to "
               "record a REFUSAL because the log is down protects nothing, and the refusal itself "
               "already means nothing was spent or booked",
    },
    {
        "action": "whatsapp_assistant.consent_refused",
        "source": "internal",
        "critical": False,
        "resource": "conversation",
        "why": "an inbound message was NOT processed because either (a) the customer's own live "
               "answer to the consent-request below was \"إنهاء المحادثة\", or (b) "
               "consent_gate.check() answered unknown under CONSENT_POLICY_ON_UNKNOWN=fail_closed "
               "(compliance-service genuinely unreachable — a real DENIED never reaches here any "
               "more since 2026-09-19: it is re-asked instead, see consent_requested below). "
               "Not critical: this is already the safe outcome (nothing was done with the "
               "customer's data), so losing the record on an audit-sink outage costs no protection "
               "the refusal itself did not already provide — same reasoning as proposal_rejected, "
               "above",
    },
    {
        "action": "whatsapp_assistant.consent_requested",
        "source": "internal",
        "critical": False,
        "resource": "conversation",
        "why": "compliance-service answered DENIED for this subject/purpose (2026-09-19: means "
               "either never asked before, or an on-record refusal — this gate treats both "
               "identically, neither final) — an interactive «متابعة»/«إنهاء المحادثة» message "
               "was sent and nothing else in this turn is processed. Not critical: the safe "
               "outcome (asking, not assuming) already happened; the customer's own next answer "
               "is what actually matters and is itself audited (consent_refused above, or nothing "
               "further to log on \"متابعة\" beyond the ordinary conversation path resuming).",
    },
    {
        "action": "whatsapp_assistant.message_attributed",
        "source": "internal",
        "critical": False,
        "resource": "conversation",
        "why": "attribution (tenant, this subject's own pseudonym, the wamid — never the message "
               "text) for a real inbound message that WAS processed, written the moment "
               "consent clears (app/core/inbound_ingest.py), so it survives past "
               "CHAT_RETENTION_DAYS purging the message content itself: if the chat is gone by "
               "the time anyone asks, this is what still proves a conversation happened, from "
               "which customer, and when. Not critical: refusing every ordinary inbound message "
               "because the audit log is briefly unreachable would take the whole assistant down "
               "to protect a record — the same trade this file already makes for "
               "consent_refused/proposal_rejected",
    },
    {
        "action": "whatsapp_assistant.outbound_capped",
        "source": "internal",
        "critical": False,
        "resource": "conversation",
        "why": "either outbound rate limiter (core/inbound_ingest.py's own outbound_allowed — "
               "per-conversation or per-number) refused a send. Logged at `warning`, which Fluent "
               "Bit deliberately never ships to error-collector (a cap tripping is expected, "
               "working behaviour, not a failure) — this is the ONLY place an operator can see or "
               "count one. Not critical: the safe outcome (nothing over-sent) already happened; "
               "losing the record on an audit-sink outage costs visibility, never safety",
    },
    {
        "action": "whatsapp_assistant.unpriced_model_used",
        "source": "internal",
        "critical": False,
        "resource": "model",
        "why": "the live ASSISTANT_MODEL_NAME had no entry in PRICING_AI_UNIT_MODEL_COSTS_JSON, so "
               "the reserve was priced at a substitute rate instead (core/ai_unit_pricing.py's own "
               "model_rate_halalas_per_1k) — an operator gap, not a reason to refuse the reply, but "
               "one that must be visible: this used to be both invisible and silently free (the "
               "flat legacy fallback is deployed at 0). Not critical: the reply itself already "
               "went out correctly either way; losing the record on an audit-sink outage costs "
               "visibility into a pricing gap, never money-safety",
    },
    {
        "action": "operator.secret_set",
        "source": "admin",
        "critical": True,
        "resource": "secret",
        "why": "a credential change is the action that most needs attribution: the previous value "
               "is gone the moment it happens, so an unrecorded rotation cannot be reconstructed, "
               "and an unattributable one is indistinguishable from an attacker's",
    },
    {
        "action": "operator.secret_set_refused",
        "source": "admin",
        "critical": False,
        "resource": "secret",
        # Added 2026-09-07 alongside the fix that made operator.secret_set fire only AFTER a
        # successful write — a refused attempt (a bad value SecretError caught) is a distinct,
        # honest event now, never folded into secret_set as if the rotation had actually happened.
        "why": "a refused credential change is worth its own trail — who tried, and why it was "
               "refused — without ever implying the old value was touched (nothing here is "
               "unrecoverable, unlike a real rotation, so this is not critical)",
    },
    {
        "action": "operator.secret_cleared",
        "source": "admin",
        "critical": True,
        "resource": "secret",
        "why": "clearing a credential silently reverts the service to whatever the environment "
               "holds, which is a behaviour change nobody would otherwise see",
    },
    {
        "action": "operator.config_changed",
        "source": "admin",
        "critical": False,
        "resource": "config",
        "why": "a live-overridden policy value (app/runtime_policy.py) changes real behaviour — "
               "which model replies, when soft-decline suppresses a pitch — with no redeploy and "
               "no other trace of who changed it or when",
    },
    {
        "action": "operator.config_change_refused",
        "source": "admin",
        "critical": False,
        "resource": "config",
        # Same reasoning as operator.secret_set_refused above — added 2026-09-07 alongside the fix
        # that made operator.config_changed fire only after a successful write.
        "why": "a refused config change is worth its own trail without implying the value actually "
               "moved; not critical for the same reason config_changed itself is not",
    },
    {
        "action": "operator.pricing_scheduled",
        "source": "admin",
        "critical": True,
        "resource": "config",
        "why": "a shop's real bill changes the day this lands (core/pricing_schedule.py) — "
               "critical, unlike an ordinary config_changed above, because a shop later disputing "
               "a charge needs this provable: who scheduled which rate, and when it was told it "
               "would take effect, not just that it eventually did",
    },
    {
        "action": "whatsapp_assistant.meta_agent_provisioned",
        "source": "internal",
        "critical": True,
        "resource": "meta_agent",
        "why": "the full Meta Business Agent onboarding sequence (core/meta_agent_provisioning.py) "
               "ran to completion for a shop's freshly-connected WhatsApp number — real Graph API "
               "state now exists on Meta's own side (an agent, a Connector, registered tools) "
               "under this shop's identity. Critical: this is the one record that can later prove "
               "the automated setup actually happened and succeeded, rather than a shop silently "
               "never getting an active agent with nothing to show why",
    },
    {
        "action": "whatsapp_assistant.meta_agent_provision_failed",
        "source": "internal",
        "critical": False,
        "resource": "meta_agent",
        "why": "the onboarding sequence stopped at a named step (ineligible number, a Graph call "
               "failing, provisioning disabled) — fire-and-forget by design (never fails the "
               "connect response itself, see connect.py's own comment), so this is the ONLY place "
               "an operator can later see which step failed and why, to retry it. Not critical: "
               "the safe outcome (nothing half-configured was left enabled) already holds; losing "
               "this record on an audit-sink outage costs visibility, never safety",
    },
    {
        "action": "whatsapp_assistant.meta_agent_rollout_enabled",
        "source": "internal",
        "critical": True,
        "resource": "meta_agent",
        "why": "Meta's own AI was switched back on for a number (owner flipped their kill switch "
               "back on, or resubscribed to feature.whatsapp) — critical because this is the record "
               "that a shop's customers are being auto-replied to by Meta's AI again, and when that "
               "started being true",
    },
    {
        "action": "whatsapp_assistant.meta_agent_rollout_disabled",
        "source": "internal",
        "critical": True,
        "resource": "meta_agent",
        "why": "Meta's own AI was switched off for a number — today only the owner's own kill "
               "switch (feature.whatsapp lapsing has no caller yet, see operations' own "
               "meta_agent_rollout_trigger.py). Critical for the same reason the opposite "
               "direction is: this is the provable moment customers "
               "stopped getting an automated reply from this shop's number",
    },
    {
        "action": "operator.pricing_schedule_cancelled",
        "source": "admin",
        "critical": False,
        "resource": "config",
        "why": "a scheduled pricing change was withdrawn before it ever took effect — nothing a "
               "shop was ever billed under, so losing the record on an audit-sink outage costs no "
               "protection the cancellation itself did not already provide",
    },
]
