# Raje3 POS/Till Integration — API Reference

**This file is generated from the code.** Every field table below is read from the Pydantic models the routes actually validate against, not typed by hand — a hand-written integration doc goes stale the moment a field changes, and an integrator who built against the page instead of the API finds out months later. The reasoning behind the design ('why') is written once, here, by a person; the fields and types are not.

A parallel Arabic document (`دليل-ربط-الكاشير.md`) covers the same four endpoints for a shop owner reading over the integration; this one is the technical reference for the engineer actually implementing the client.

---

## Authentication

**One machine credential per shop**, issued as an OAuth2 client-credentials grant. Send it as a normal Bearer token:

```
Authorization: Bearer <your access token>
```

**The tenant (shop) is read from the token itself, never from the request body** — there is no `tenant` field on any request below, on purpose. A credential minted for one shop is physically unable to name another one; there is no field to set.

**One capability: `operations.record`.** It can record a visit, read what belongs to that visit's customer, and hand over a reward. Nothing else — not billing, not other shops, not any admin surface.

**A token with no tenant claim is refused outright** (not widened to "every shop") — every endpoint below answers as if nothing was sent at all.

**Sandbox:** we provision a real test shop on the exact same routes, the exact same rules and the exact same refusals — free, uncharged, not counted as a real customer. There is no separate sandbox credential: you test with the same credential you will run in production, so whatever passes in sandbox is proven to work for real.

---

## Rate limits

**Customer lookups (`GET /customer`) are budgeted as a RATIO of visits you have actually recorded, not a fixed window.** A busy till that is genuinely recording sales never comes close to the ceiling; a credential making far more lookups than the visits it records does, because that is the one shape data extraction takes. Over the budget, the response is **`429`** with a message explaining why — never `403`: the credential is still valid and was never revoked.

---

## 1. Post visits — `POST /api/v1/till/visits`

Batch of up to 50 visits. **The response reports a verdict per item** — `accepted`, `duplicate`, or `rejected` with a reason — never all-or-nothing: one permanently invalid item in a batch must never block the other 49 behind it in the same post.

**Match each result back to what you sent by `index`** — the visit's position in the `visits` array you posted (0-based). Results are ordered by it and the list is exactly as long as what you sent. Do not match on `idempotency_key`: if you did not send one, we derive it from your invoice number, and the string that comes back was never one you held.

### Visit fields

| Field | Type | Required | Why |
|---|---|---|---|
| `phone` | str | no | The shop's customer's phone number. Without it we cannot attribute the visit or message them. |
| `name` | str | no | Their name, if you have it. Optional. |
| `plate` | str | no | Vehicle plate — used in practice by tyre shops, car washes and upholstery shops. |
| `branch_id` | str | yes | The branch where this happened. Required, and must be a branch this shop actually has — an id we don't recognise is rejected and named back to you. |
| `operator_id` | str | no | Your own cashier account id. Stored as sent — we do not build a second accounts system. |
| `meter` | int | no | Odometer reading, for the vehicle sector. |
| `note` | str | no | A free-text note, visible to the owner. |
| `lines` | list[TillLineIn] | no | Invoice line items. The shop's catalogue is built from these automatically — send them as they are. |
| `invoice_id` | str | no | Your own invoice number. The best idempotency key, because it is your own identifier for this exact sale. |
| `idempotency_key` | str | no | Your own idempotency key, if you have one. |
| `occurred_at` | int | no | When the sale happened, by your own clock (unix seconds). Used as the idempotency key when there is no invoice number. |
| `package_id` | str | no |  |

### Invoice line

| Field | Type | Required | Why |
|---|---|---|---|
| `product_id` | str | no | Your own product/item id. |
| `name` | str | no | The product/service name exactly as on your invoice — the shop's catalogue is built from this. |
| `qty` | float | no | Quantity. |
| `amount_minor` | int | no | Amount in halalas — never riyals, never a decimal. |

### Deduplication — the one rule with no exception

**Every visit must carry at least one of:** `idempotency_key`, `invoice_id`, or `occurred_at`. Without any of the three the visit is **rejected**, naming all three in the reason.

Why: retrying after a lost reply is the normal case for a till, and without a stable key one sale becomes two visits — doubling the customer's history, their reminders, and their points.

### Example request

```http
POST /api/v1/till/visits
Authorization: Bearer <token>
Content-Type: application/json

{
  "visits": [
    {
      "phone": "0501234567",
      "branch_id": "brn_main",
      "invoice_id": "INV-2026-00042",
      "lines": [
        {"product_id": "sku_wash_1", "name": "Full wash", "qty": 1, "amount_minor": 5000}
      ]
    }
  ]
}
```

### Example response

```json
{
  "accepted": 1,
  "total": 1,
  "results": [
    {"index": 0, "status": "accepted", "idempotency_key": "inv:<tenant>:INV-2026-00042"}
  ]
}
```

A rejected item looks like:

```json
{"index": 3, "status": "rejected", 
  "reason": "unknown branch_id «brn-typo» — send one of this shop's own branches"}
```

---

## 2. Look up a customer — `GET /api/v1/till/customer`

Query with `phone` or `plate`. Answers whether they are a known customer, their name, visit count, points balance, and what they can redeem right now.

**A new customer is `found: false`, never a 404** — a first-time customer is the ordinary case at a counter, not a fault to log and retry.

**Three states that must not be conflated:** no such customer · points temporarily unreadable (`points_unavailable: true`) · no loyalty programme at this shop at all (the points section is simply absent). A `0` is never sent in place of "could not read it" — telling a customer holding 300 points that they have none creates a complaint over nothing.

### Example: known customer, loyalty programme active

```json
{
  "found": true,
  "name": "Ahmad",
  "visits": 12,
  "points": 340,
  "to_next_reward": 60,
  "manager_threshold": 500,
  "rewards": [
    {"id": "rwd_free_wash", "name": "Free wash", "cost": 300, "needs_approval": false}
  ]
}
```

`needs_approval: true` on a reward means it is above this shop's manager-approval threshold — see `approved_by` on the redeem endpoint below.

### Example: brand-new customer

```json
{"found": false}
```

### Example: customer known, points temporarily unreadable

```json
{"found": true, "name": "Ahmad", "visits": 12, "points_unavailable": true}
```

---

## 3. Redeem a reward — `POST /api/v1/till/redeem`

| Field | Type | Required | Why |
|---|---|---|---|
| `phone` | str | no | The phone number of the customer redeeming. |
| `plate` | str | no | Or their plate, if that is how you identify customers. |
| `reward_id` | str | yes | The reward id, exactly as returned by GET /till/customer. |
| `idempotency_key` | str | yes | Your key for THIS operation — required. Without a stable key, a retry spends the customer's points a second time. |
| `actor` | str | no | The cashier account that handed the reward over. |
| `approved_by` | str | no | Name/id of the manager who approved this — required ONLY for a reward above this shop's approval threshold (flagged to you as `needs_approval` from GET /till/customer). Without it, those specific rewards are always refused. **UNVERIFIED free text** — use `approver_operator_id`/`approver_ticket` below instead for a real, checked identity. |
| `approver_operator_id` | str | no | The id of the operator whose PIN was just verified via POST /till/operators/verify-pin — the VERIFIED path; overrides `approved_by` when sent. |
| `approver_ticket` | str | no | The ticket issued by POST /till/operators/verify-pin — good for a few minutes only. |
| `branch_id` | str | yes | The branch where this happened. Required, and must be a branch this shop actually has — an id we don't recognise is rejected and named back to you. |

**`idempotency_key` is required, with no default we can fill in for you** — a key we mint ourselves would be new on every retry, and a doubled redemption spends the customer's points twice.

**A refusal comes back as a full sentence** — read it to the customer directly. Distinguish `REFUSED` (final — e.g. insufficient balance) from `UNAVAILABLE` (transient — retry).

### Example request

```json
{
  "phone": "0501234567",
  "reward_id": "rwd_free_wash",
  "idempotency_key": "redeem-2026-00042",
  "branch_id": "brn_main",
  "actor": "cashier_3"
}
```

### Example responses

```json
{
  "ok": true,
  "transaction_ref": "rdm_...",
  "discount_halalas": 5000,
  "reward_name": "Free wash",
  "cost": 300,
  "balance": 40,
  "duplicate": false
}
```

`duplicate: true` means this exact `idempotency_key` was already redeemed — the SAME receipt is returned, nothing is spent a second time.

```json
{"ok": false, "reason": "REFUSED", "message": "رصيده لا يكفي"}
```

```json
{"ok": false, "reason": "NOT_FOUND", "message": "لا يوجد عميل بهذا الرقم."}
```

`transaction_ref` is what the receipt must carry — print it on the paper receipt so it has a second trail.

---

## 4. Apply an offer to a visit — `POST /api/v1/till/offer/apply`

**The offer the customer is holding is applied to the visit — never guessed.** Nothing spends an offer just because a visit arrived; `reminders` alone decides which offer applies, because it alone knows what was sent, its scope, and its expiry.

| Field | Type | Required | Why |
|---|---|---|---|
| `visit_id` | str | yes | The id of the visit just recorded — the offer is stamped onto THIS, never onto the offer itself. |
| `phone` | str | no | The phone number of the customer holding the offer. |
| `plate` | str | no | Or their plate, if that is how you identify customers. |
| `actor` | str | no | The cashier account that applied the offer. |

**One per visit** — a second apply on the same visit returns the SAME offer and spends nothing further: a second tap at the counter is one intention, not two discounts.

### Example request

```json
{"visit_id": "vis_...", "phone": "0501234567", "actor": "cashier_3"}
```

### Example responses

```json
{"applied": true, "offer": {"ref": "off_...", "text": "20% off your next wash", 
  "used_at": 1735689600}}
```

```json
{"applied": false, "reason": "لا يوجد عرضٌ ساري يشمل هذه الزيارة"}
```

---

## 5. Bookings — `GET /api/v1/till/bookings` and `POST /api/v1/till/bookings/{booking_id}/attend`

**A shop running both bookings and an integrated till** needs a way to tell a booking that its customer actually showed up and paid — without this, the booking calendar and the till's own sale ledger silently disagree about what happened.

**The first route lists a customer's OPEN bookings** — send their phone or plate, get back anything not yet attended, cancelled, or marked no-show:

```json
{"found": true, "bookings": [{"id": "bkg_123", "starts_at": 1786860000, "branch_id": "brn_1", "service_ids": ["svc_1"], "package_id": ""}]}
```

**The second actually confirms attendance**, turning the booking into a real visit:

| Field | Type | Required | Why |
|---|---|---|---|
| `phone` | str | no | The phone number of the customer who made the booking. |
| `plate` | str | no | Or their plate, if that is how you identify customers. |
| `branch_id` | str | no | The branch this happened at, if you want to confirm the booking belongs to this specific branch. Optional. |
| `occurred_at` | int | no | When attendance actually happened, by your own clock (unix seconds). Empty means now. |

**Safe to retry** — a second tap on an already-attended booking returns the SAME booking with no further effect: a retry after a dropped connection cannot double the visit or spend a reward twice.

```json
{"ok": true, "booking_id": "bkg_123", "status": "attended"}
```

**A refusal is a sentence to read aloud, never a bare code:**

```json
{"ok": false, "reason": "NOT_FOUND", "message": "لا يوجد حجز بهذا الرقم يخصّ هذا العميل."}
```

---

## 6. Branches — `GET /api/v1/till/branches`

Your shop's own active branches — validate `branch_id` before sending it, rather than discovering a typo only by having a visit rejected:

```json
{"branches": [{"id": "brn-main", "name": "الفرع الرئيسي"}]}
```

---

## 7. Credential status — `GET /api/v1/till/status`

Is your programmatic link actually active right now, and how much of today's lookup allowance is left — ask this BEFORE sending a batch of sales or a customer lookup, not after being refused:

```json
{"feature_api": "active", "feature_visit": "active", "lookup_allowance_remaining_today": 187}
```

`"unknown"` means we could not ask — neither a refusal nor an approval.

---

## 8. A real, verified approver — `POST /api/v1/till/operators/verify-pin`

**Before this door, ANY text in `approved_by` was accepted with no check at all.** This actually verifies the operator's real 4-digit PIN and issues a short-lived ticket — send it with `approver_operator_id` on `/till/redeem` instead of a free-typed name.

| Field | Type | Required | Why |
|---|---|---|---|
| `operator_id` | str | yes | The operator's id — from this shop's own staff list. |
| `pin` | str | yes | The operator's own 4-digit PIN. |

```json
{"ok": true, "operator": {"id": "opr_1", "name": "خالد"}, "ticket": "...", "ticket_ttl": 300}
```

---

## 9. Rating request, on demand — `POST /api/v1/till/rating-request`

Builds no new send path — pulls an already-scheduled rating request for this customer forward to "due now", so it arrives in minutes instead of the shop's usual delay. Answers a clear refusal, never an error, when nothing is scheduled (no rating app, or already sent):

| Field | Type | Required | Why |
|---|---|---|---|
| `phone` | str | no | The phone number of the customer who made the visit. |
| `plate` | str | no | Or their plate, if that is how you identify customers. |
| `asset_id` | str | no | The vehicle id, vehicle-sector shops only — if the rating schedule is keyed by the vehicle, not the customer. |

```json
{"ok": true, "message": "سيصل طلب التقييم للعميل خلال دقائق قليلة."}
```

---

## 10. Grant a shop-to-shop coupon — `POST /api/v1/till/coupons/grant`

**For stores and sites that broker a subscription between us and another shop already registered on Raje3**: send your own order number and the beneficiary shop's phone number, and we grant the discount straight onto THAT shop's own subscription with us — **never against your own customer's invoice**; this endpoint has nothing to do with your customers.

| Field | Type | Required | Why |
|---|---|---|---|
| `phone` | str | yes | The BENEFICIARY shop's own registration phone number (another shop registered on Raje3 — never your own customer) — the same number that shop signed up with. |
| `percent` | int | yes | The discount percent on that shop's OWN platform subscription with us. Silently clamped to your own shop's current cap if you send more. |
| `app_keys` | list[str] | no | Specific app keys to discount when `general` is false, e.g. `feature.bookings`. |
| `order_id` | str | yes | Your own order/invoice number — **required**. **The only thing that prevents a duplicate grant**: resending the same value returns the exact first result again, never a second discount. |

**Safe to retry**: resending the same `order_id` returns the exact same first result, never a second discount — a retry after a dropped connection costs the beneficiary shop nothing extra.

```json
{"ok": true, "reason": "granted", "attempt": {"id": "ctatt_...", "outcome": "granted", 
  "percent_requested": 15, "grant_ids": ["ctg_..."]}}
```

**Refused because your own shop does not hold the coupons app:**

```json
{"ok": false, "reason": "NOT_SUBSCRIBED", 
  "message": "اشتراك هذا المحل لا يشمل تطبيق الكوبونات — أضفه من «الباقات» ليعمل هذا المسار."}
```

---

## What we never send you

**The customer's pseudonym** (`subject_ref`): our own cross-service join key, which you have no use for — you identify your customer by the phone number you already hold. A durable cross-service identifier sitting in a third party's database with no purpose it serves is a risk with no matching benefit.

