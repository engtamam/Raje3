# DSAR access-request redesign — study (2026-09-13)

Scope: study only, no code changed here. Companion to the settled decision to delete
`per_dsar_code` and its current wrong-flow parts now. This documents (1) the exact deletion
scope, (2) whether anything else in `services/` creates or reads an access-type DSAR, and
(3) a design for a proper shop-facing access-request flow, mirroring the erasure pattern that
already works.

## 1. Exact deletion scope

Every reference to `per_dsar_code` / `dsar-code` / `DsarCodeIn` / `send_dsar_code` in
`services/*` and the console:

- `services/reminders/app/api/internal.py:885-961` — `DsarCodeIn` model and the
  `POST /internal/reminders/dsar-code` route (`send_dsar_code`). Delete both.
- `services/reminders/app/api/v1/owner.py:896-919` — `DsarCodeOut` model and
  `POST /api/v1/reminders/dsar-code` (`send_my_dsar_code`), which only wraps `send_dsar_code`
  with the caller's own token subject. Delete both; delete the `from app.api.internal import
  DsarCodeIn, send_dsar_code` local import at line 912 with it.
- `services/reminders/app/manifest.py:109` (`/internal/reminders/dsar-code`, tier `internal`)
  and `:132` (`/api/v1/reminders/dsar-code`, tier `user`) — remove both manifest rows, or the
  safety gate will flag routes advertised in the manifest that no longer exist in code.
- `services/reminders/app/user_actions.py:69-77` — the `reminders.send_dsar_code` action
  entry (id, label, path, capability, help). Delete the whole dict.
- `services/reminders/app/core/reasons.py:290-299` — the `privacy_code` `Reason` entry
  (`template_type="per_dsar_code"`, `owner_can_switch=False`, `owner_can_retext=False`).
  Delete the whole `Reason(...)` block.
- `services/reminders/app/core/gate.py:64` — `"per_dsar_code"` in `WINDOW_EXEMPT_TYPES`.
  Remove that one string from the frozenset (keep the surrounding comment block or trim it —
  it only makes sense next to the entry it explains).
- `services/operations/data/templates.seed.json:615-≈690` — both `per_dsar_code_masculine`
  and `per_dsar_code_feminine` template objects. Delete both whole objects (masculine block
  starts at line 616 `"name": "per_dsar_code_masculine"`, feminine at line 653; each runs to
  its closing `}` a few lines after the `examples` array — read the surrounding commas
  carefully so the JSON array stays valid).
- `apps/console/src/screens/AccountPanes.tsx:862-... (DataPane)` — the `deliver =
  action(catalog, 'reminders.send_dsar_code')` call at line 893 and the `codeSent` branch
  (889-911) that depends on it. **Important, read before deleting**: this is NOT the
  end-customer violation path — see §2. It is the shop owner's own self-service DSAR against
  Raje3 (`compliance.open_my_dsar` → `/api/v1/compliance/me/dsar`, a `platform` route, kept).
  Deleting `reminders.send_dsar_code` removes the *code-delivery* half of this working,
  already-correct owner-facing flow, not just a broken one. The `ask()` function should
  collapse to just recording the request (`opened`) and reporting `recordedNoCode` always,
  until the redesign in §3 gives it a real delivery channel again. Flag this explicitly to
  the owner — it is a real (small) regression riding along with the deletion, distinct from
  the violation being fixed.
- `apps/console/src/screens/Messages.tsx:352` — `privacy_code: 'per_dsar_code'` row in the
  reason→template-type map used for template preview. Delete the row.
- `services/reminders/tests/unit/test_models_stores.py` and
  `services/reminders/tests/unit/test_auditable_actions.py` — grep both for `dsar` and
  remove/adjust any assertion that touches the deleted route, model, or reason.
- `ci/check_template_libraries.py:13-18` — a comment narrating PAST drift history (`per_weekly_digest`,
  `wrn_safety_notice`, `per_dsar_code` "existed in the document and in the code that sends them,
  and were never submitted for anybody"). This is historical narrative, not an active
  exemption or live check — no functional change needed, but note it now names one template
  that no longer exists; leaving the sentence as history is fine, editing it is optional.
- `docs/وصف-منصة-راجع.md`:
  - Line 1377 — the `per_dsar_code` / `priority` row in the exemption table.
  - Line 3612 — the "25 ← 26" changelog note naming `per_dsar_code`'s addition. This is a
    dated changelog entry; per this project's own convention old changelog entries are not
    rewritten (see `commits-in-english.md`'s sibling rule for commit history) — leave it, add
    a new dated line noting the removal instead of editing history.
  - Lines 3784-3794 — the full `per_dsar_code` template section (masculine/feminine body
    table, the "carries nothing of his" paragraph, the night-quiet exemption paragraph).
    Delete the whole section (it is entirely about the template being deleted).
- `docs/message-shape-taxonomy-2026-09-13.md:45` — the `per_dsar_code` row in the shape
  table. Delete the row.
- `docs/فحص-الجودة-15.md:212` — a matching line (long, omitted above); read it directly and
  remove/update whatever it asserts about `per_dsar_code`.

**Do NOT touch** `platform/services/compliance-service/*` — separate codebase/team.

**Heads-up owed to the platform team**: `platform/services/compliance-service`'s
`send_dsar_code`-adjacent call is the *outbound* side — `internal.py:922-925` in reminders is
the caller that fetches `{COMPLIANCE_SERVICE_URL}/internal/compliance/dsar/{id}/verification-code`
from compliance-service, and reminders' own `POST /internal/reminders/dsar-code` is what
compliance-service (or anything else) would call to ask reminders to deliver. Grep shows
nothing today in `platform/` actually calls `POST /internal/reminders/dsar-code` (only
reminders' own admin console UI called `POST /api/v1/reminders/dsar-code`, the user-tier
wrapper) — so no live outbound call from compliance-service breaks silently. What *does*
change: any DSAR compliance-service creates from here forward has no automatic way for the
subject to receive their verification code (see §2) — worth one line to the platform team so
they know delivery is gone, even though no route call breaks.

## 2. Is anything else in `services/` creating or reading an access-type DSAR?

No. The only creation path for a DSAR against an **end customer** (not the shop owner) is
`platform/services/compliance-service/app/api/v1/compliance.py:262-277`
(`POST /dsar`, `_ADMIN`-gated), surfaced only by
`apps/console/src/admin/AdminCompliance.tsx` (`compliance.open_dsar`, line 128) — a
RAJE3-INTERNAL admin screen under `apps/console/src/admin/`, confirmed reading the file
directly (§ "dsar" tab, `ACTION_IDS.dsar.row` includes `compliance.open_dsar`,
`compliance.verify_dsar`, `compliance.process_dsar`, all admin actions). There is no
customer-facing or shop-owner-facing UI anywhere in `services/` or `apps/console/src/screens/`
that opens an access, export, or correction DSAR about a customer. (Erasure is the one
exception — see §3.)

Separately, `apps/console/src/screens/AccountPanes.tsx`'s `DataPane` calls
`compliance.open_my_dsar` → `platform/.../compliance.py:280-301` (`POST /me/dsar`, `_SELF`).
This is real and already correct, but it is the **shop owner's own** DSAR against Raje3 (the
owner is Raje3's account holder here, exercising rights over their own business's data held
by the platform) — not a request about an end customer. It uses the same `per_dsar_code`
delivery for convenience but has nothing to do with the end-customer violation. This is the
regression flagged in §1.

**Can `verify_dsar` proceed without ever receiving a code?** No, by construction:
`platform/services/compliance-service/app/core/dsar_service.py:63-72`'s `verify()` compares
the caller-supplied `token` against `d.verification_token` with `hmac.compare_digest` — an
exact secret match, minted once at creation
(`compliance.py:276`, `:301`, and `dsar_service.py:56`,
`secrets.token_urlsafe(32)`) and never re-derivable. With `per_dsar_code` gone and nothing
else delivering that token to an end customer, any **access-type DSAR opened today through
AdminCompliance.tsx against a customer** is permanently stuck at `verified: false` — there is
no automated channel left, full stop. (A Raje3 staffer could theoretically copy the
one-time `verification_token` from the `open_dsar` response — `compliance.py:276` returns it
"once, to send to the subject" — and read it to the customer by phone, but that path is not
wired into `AdminCompliance.tsx` today, and doing it that way would itself require Raje3
staff to be on the phone with the shop's customer, which is exactly the pattern being
designed away in §3.) This confirms the deletion is safe to do now — nothing today completes
that verification loop anyway — but it does mean access-type DSARs cannot be verified at all
until the redesign ships.

## 3. Redesign: shop-facing access request, mirroring erasure

**The erasure pattern, confirmed precisely.** `apps/console/src/screens/Customer.tsx:152,
232, 721-778` — a single-customer profile screen the shop owner/staff already uses. It holds
an `eraseAction = action(catalog, 'operations.erase_customer')` (defined in
`services/operations/app/user_actions.py:137-140`: `POST /api/v1/field/customers/{customer_id}/erase`),
rendered as a plain button behind a two-step confirm (`eraseAsked` → confirm/cancel), calling
`{ customer_id: id }`. No phone number, no WhatsApp code, no external contact — the shop
owner is looking at a record they already have open, presses one button, and
`services/operations/app/core/erase_customer.py` does the deletion server-side.
**Nothing about identity verification happens on this path at all** — the shop already knows
who its own customer is (they are looking at that person's record); the "proof of channel"
problem that `per_dsar_code` exists to solve was invented by the *admin* flow, not by erasure.

**Does the customer need to prove anything for access, if erasure doesn't ask them to?**
Worth separating two different risks the code is protecting against:
- *Erasure*: the shop already has the record open; the person taking the action is shop
  staff, accountable and logged (`erase_customer` presumably logs an actor — worth confirming
  at build time). The "wrong person's data destroyed" risk is bounded by staff being the
  actor, not the subject.
- *Access/export*: handing over a person's own data file is a disclosure — if the wrong
  person receives it, that is itself a breach. This is why PDPL Article 4 verification
  matters more here than for erasure, and why the current design (rightly) does not just let
  a staffer type in "yes, this is really him" and get the file.

**Concrete proposed shape**, smallest addition that keeps the verification safeguard while
fixing the actual violation (which is the *admin-screen* part, not the WhatsApp-code part):

1. **Contact stays with the shop.** No change needed — the customer already calls/visits
   the shop today; nothing to build here.
2. **A new console action, `operations.request_customer_access`** (name TBD), added next to
   `operations.erase_customer` in `services/operations/app/user_actions.py`, rendered as a
   second button in `Customer.tsx` beside the existing erase control (same
   confirm-then-fire shape, `customer_id` from the record already open). Server-side, this
   route does NOT reinvent DSAR machinery — it calls into
   `platform/services/compliance-service`'s existing `POST /dsar` with `type=access`, the
   same way `AdminCompliance.tsx` does today, except the caller is now the shop's own
   operations backend on the shop owner's behalf (an internal service-to-service call,
   authenticated the way `services/operations` already calls other internal platform/service
   routes — e.g. `services/operations/app/adapters/consent_gate/http.py` is the existing
   precedent for operations calling out to a compliance-shaped backend). This is genuinely a
   small addition: one new user_action, one new thin route in operations that proxies to the
   existing `/dsar` create call with `type=access` and the shop's own tenant, one new button
   in `Customer.tsx`.
3. **Verification: `per_dsar_code` was never the violation.** Confirmed directly in
   `services/reminders/app/api/internal.py:940-946` — the delivery send already sets
   `sending_identity=body.tenant`, i.e. the message is rendered and sent under the
   **shop's own** registered WhatsApp identity, exactly like every other template in
   `templates.seed.json`. A customer receiving this code today has no way to tell it apart
   from any other message their salon or car wash sends them — it never says "Raje3." The
   actual violation was entirely upstream of delivery: a Raje3 staffer had to be the one to
   press "open DSAR" in `AdminCompliance.tsx`, which meant a customer had to reach Raje3
   support first to trigger that button. Once step 2 lets the shop's own console create the
   DSAR (`type=access`) and trigger delivery itself, the *exact same*
   `per_dsar_code` template and `send_dsar_code`-shaped delivery route can be rebuilt
   essentially unchanged — the difference is only who is authorized to call "create DSAR
   for this subject," not how the code reaches the customer.

**Net assessment: this is a small redesign, not a large one.** The needed shape is
"give the shop owner's own console the same kind of button erasure already has, wire it to
`type=access` on the same underlying DSAR machinery compliance-service already exposes, and
rebuild the delivery route almost identically to the one just deleted (still WhatsApp, still
under the shop's own identity, still fetching the code from compliance rather than minting
it)." The one open design question worth the owner's explicit decision before building: should
`services/operations` call compliance-service's `/dsar` directly (thin proxy, fastest to
ship, couples operations to compliance-service's contract), or should this go through a
narrower internal endpoint compliance-service exposes specifically for "a shop's own console
opened this on a customer's behalf" (cleaner boundary, more to build, and requires
coordination with the platform team since it is their service). Recommendation: start with
the thin proxy — it is the same shape `AdminCompliance.tsx` already uses today, just called
from a different, correctly-scoped place, and it does not require the platform team to ship
anything new before this can exist.
