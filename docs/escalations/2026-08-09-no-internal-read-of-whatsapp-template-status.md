# No internal route to read WhatsApp template status

**Service:** `notification-service`
**Severity:** medium — every adopter either wastes sends or duplicates the registry

## What is missing

`notification-service` exposes:

- `POST /internal/whatsapp/templates/sync` — internal, reconciles a tenant's pending templates
- `GET  /api/v1/whatsapp/templates` — **user tier**, requires the `notifications.templates` capability

There is no internal, token-authenticated way for a peer service to ask *which templates are
approved for this tenant*.

## Why a peer needs it

A template belongs to one WhatsApp Business Account, so approval is per tenant: the same text is
approved for one establishment and pending for another. A sending service that chooses a template
by TYPE — "the service reminder, in this shop's tone" — has no way to prefer an approved one.

It therefore sends, and `notify()` correctly refuses. But by then the send is spent, the reminder
has taken its slot in the daily cap, and the failure reads as an error nobody can act on.

## Why the obvious workarounds are wrong

- **Mint a user token in the sending service.** That needs the signing private key, which lives in
  identity-service and must stay there. A second service holding it makes one compromise a
  platform-wide forgery.
- **Keep a copy of the statuses.** A second copy of another service's state, updated by a webhook
  we do not receive, drifting the first time a sync runs.

## Suggested fix

An internal counterpart to the existing list:

```
GET /internal/whatsapp/templates?tenant=<t>&status=approved
```

Same handler, internal token, tenant as a parameter rather than from the principal — exactly the
shape `/internal/whatsapp/templates/sync` already has.

## Our position meanwhile

We do not pre-check. `reminders` reads the DELIVERY status returned by `/internal/notify` and
treats a refusal as a deferral: the schedule goes back to pending and the message goes when the
template clears. That is correct, and it costs one wasted call per reminder for a shop whose
library is still under review — acceptable for the first day of an account, and not acceptable as
a permanent design.

We removed a `choose(approved=...)` parameter the same day we wrote it, because nothing could
supply it. A parameter nobody can pass is a promise the code does not keep.
