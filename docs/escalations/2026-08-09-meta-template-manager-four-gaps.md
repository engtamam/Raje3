# The Meta template manager cannot submit a template that has variables

**Service:** `notification-service`
**File:** `app/adapters/whatsapp_templates/meta.py`, `MetaTemplateManager`
**Severity:** blocking — every template with a placeholder is rejected, and one status is unreadable
**Verified against:** Meta's own documentation, August 2026 — *Template fundamentals* and the
*Template API* reference

Four findings, in the order they will hurt.

---

## 1 · No `example` — and Meta requires one for every parameter

`submit()` builds:

```python
components = [{"type": "BODY", "text": body}] if body else []
```

Meta's template documentation is explicit: *"Upon template creation, you must include an example
value for each parameter"* when a component's string contains variables. The submission is refused
without it.

Every template in our library has at least one placeholder, so **not one of them can be submitted
through this adapter today**. It is not a degraded path; it is a hard stop, and it appears as a 400
from Graph with a reason the adopter has to decode.

The shape Meta expects:

```json
{
  "type": "BODY",
  "text": "أهلاً {{1}}، تم تسجيل زيارتك لدى {{2}}.",
  "example": { "body_text": [["محمد", "مغسلة النخيل"]] }
}
```

The port already carries `variables` — an ordered list — so the adapter has everything it needs.
Whether that list holds example VALUES or descriptions is the adopter's choice today; making it
example values, and documenting that, is the smallest change that makes the driver usable.

## 2 · `PAUSED` and `DISABLED` fall through to "pending", for ever

```python
_META_TO_STATUS = {"APPROVED": "approved", "REJECTED": "rejected", "PENDING": "pending",
                   "IN_APPEAL": "pending", "PENDING_DELETION": "pending"}
...
_META_TO_STATUS.get(meta_status, "pending")
```

Meta's documented statuses include `PAUSED` and `DISABLED`. Neither is mapped, so the default
turns both into `pending` — and a `pending` template is one the operator waits on. **They will wait
for ever**, because a paused template is not under review and a disabled one never returns.

This is worse than a cosmetic mapping gap, because of what causes those states: Meta pauses a
template for *"recurring negative feedback from customers, or low read-rates"*, and disables it for
recurring negative feedback. That is the single failure a messaging product most needs to see, and
this reports it as "still being reviewed".

`PAUSED` and `DISABLED` need to be distinct terminal-ish states in the registry, not folded into
either `pending` or `rejected`: a paused template can come back and a rejected one cannot.

## 3 · One WABA for the whole service

```python
WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""       # WABA id
...
_build_template_manager(settings)             # built once, from settings
```

The manager is constructed once from configuration, so the whole deployment submits into a single
WhatsApp Business Account.

That is right for a single-brand adopter and wrong for a multi-tenant one. A template belongs to
one WABA, and any product whose customers message under **their own** name and number has one WABA
per tenant. `build_notifier(request, tenant)` already scopes the provider pool per tenant, so the
service clearly understands per-tenant WhatsApp credentials — the template manager is the one place
that does not.

Suggested: resolve the manager per tenant from the same credential source the provider pool uses,
falling back to the configured WABA when a tenant has none.

## 4 · Graph v19.0

`_DEFAULT_BASE = "https://graph.facebook.com/v19.0"`, while Meta's current documentation references
v23.0. Not urgent, but Graph versions are deprecated on a schedule and a pinned old version becomes
an outage on a date nobody has in a calendar.

---

## How these were found

By reading Meta's documentation against the adapter, before attempting a live submission. Every one
of them would otherwise have been discovered as a rejection hours after a submission, against
template names that cannot be reused or renamed once burned.

## What we are doing meanwhile

Nothing that works around them, because there is no workaround for (1): a template with variables
cannot be created without examples, and the adapter is the only thing that talks to Graph. Our
library is registered in the registry and can be submitted the moment the adapter can carry an
example. `WHATSAPP_CHAIN` stays `console` in our values until then, which auto-approves for
development and sends nothing to Meta.
