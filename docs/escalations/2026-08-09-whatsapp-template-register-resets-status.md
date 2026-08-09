# `WhatsAppTemplateRegistry.register` silently un-approves an approved template

**Service:** `notification-service`
**File:** `app/core/whatsapp_templates.py`, `WhatsAppTemplateRegistry.register`
**Severity:** high — a re-registration takes a live establishment off the air, with no error

## What happens

`register()` is an upsert. It preserves `id` and `created` when the template already exists, and
then constructs the row with `status=PENDING` unconditionally:

```python
t = WhatsAppTemplate(
    id=existing.id if existing else uuid.uuid4().hex,
    tenant=tenant, name=name, language=language, category=cat, body=body, variables=vs,
    status=PENDING, created=existing.created if existing else _now())
```

So registering a template that is already `approved` — with identical content — moves it back to
`pending`. The send path then refuses it, correctly and by design:

```python
if tmpl.status != "approved":
    ... error=f"whatsapp template not approved: {tmpl.status}"
```

## Why it matters more than it looks

The natural operation is "make sure this establishment has the library". Anyone adding one new
template re-runs that over the whole set, and every other template in the account goes back to
pending. Every business-initiated message that establishment sends then fails, until each is
re-submitted and re-reviewed by Meta — hours at best.

Nothing reports it. The register calls all return 201, the rows are all present, and only the
`status` field changed.

## Found by

Running our seeder twice against a live tenant and reading its own counters: the second run
reported `registered=72 existing=0`, which is not what "already registered" should look like.

## Suggested fix

Preserve the status when the content is unchanged, and reset to `pending` only when `body`,
`variables` or `category` actually differ — a template whose text changed genuinely does need
re-approval, and one whose text did not, does not.

```python
unchanged = existing and existing.body == body and existing.variables == vs             and existing.category == cat
status = existing.status if unchanged else PENDING
```

Alternatively make `register` refuse an existing (tenant, name, language) outright and require an
explicit `update`, so that un-approving is something a caller asks for rather than something that
happens to them.

## Our workaround

`deploy/seed/seed-templates.sh` reads the registry first and registers only names that are absent.
That is correct for us and does not help any other adopter, who will meet this the first time they
re-run their own provisioning.
