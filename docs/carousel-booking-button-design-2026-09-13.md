# One coherent design: how a campaign message opens a real booking

Traced against the actual code in this checkout (`platform` pinned at `v0.19.33`,
`main`/`smart-booking-scheduling` branch of the outer repo). Every claim below cites a
file; nothing is asserted from memory of an earlier plan.

## 1. Decision table

| Type | 0–1 items (single/flat) | ≥2 items (carousel-eligible) |
|---|---|---|
| `mkt_offer`, `mkt_winback`, `mkt_personal_occasion` (BOOKING_TYPES) | **Flow** button (native popup), if shop owns `feature.bookings` (`shape.for_send`, `services/campaigns/app/core/shape.py:132`). Else PLAIN, no button. | **Carousel**, quick-reply `carousel:{kind}:{id}` per card, only if `card_button` (`_card_button_allowed`, `dispatch.py:284`) — needs bookings + assistant + AI on. Meta forbids `flow` sub-type on cards (`whatsapp_carousel.py:18`), so this is the *only* legal button here regardless of preference. |
| `mkt_loyalty_activation`, `mkt_announcement`, `awr_care_tip` (non-booking) | **PLAIN, no button at all** today (`shape.py:130`: carousel branch requires `card_count>=2`; the Flow branch requires `opens_booking`, which `opens_booking_for` never grants outside `BOOKING_TYPES`, `shape.py:105`). | **Carousel**, same quick-reply mechanism as above, gated by the same `card_button` — these three joined `CAROUSEL_TYPES` on 2026-09-13 specifically to replace an illegal free-text "owner" blank with the catalogue multi-select (`shape.py:56-61`). |

The owner's stated preference ("Flow wherever legal") only has room to act in the
top-left cell — it is already implemented there. Every carousel cell is quick-reply by
Meta's own hard rule, not by choice (fact #2). So there is exactly one open question:
**should the single-item cells for the three non-booking types gain a button at all?**
See §2.

## 2. Should the 3 non-booking types get a single-item button?

No — and this is not a technical gap, it's the goal itself. `shape.py`'s own module
docstring (lines 3-7) names the reasoning precisely: only three texts "end in an
intention the customer cannot act on" — winback, personal-occasion, offer — because
their whole point is getting him back through the door for an appointment. A loyalty
reward ("تقدر تستبدلها في زيارتك الجاية") is redeemed **at the counter on a visit that
already happens on its own rhythm**, not booked from the message; a care tip
(`awr_care_tip`) asks for nothing; an announcement (`mkt_announcement`) "asks for
nothing at all" (`shape.py:46`, verbatim). Opening a booking Flow under any of these
would be advertising an action the message never asked for — the exact anti-pattern the
docstring calls out for `mkt_announcement` by name.

**Verdict: leave `BOOKING_TYPES` (3 types) exactly as is.** The single-item case for the
other three stays PLAIN with no button, forever — not a placeholder, an intentional
absence (per this codebase's own "no placeholder drift" convention). Nothing to build.

## 3. The `button_item_id`/`button_kind` addition to `HttpSender.send()` (commit 6eff60f2) — DEAD CODE, remove it

Traced the full call chain:

1. `dispatch.py:220-257` calls `self._sender.send(...)` — but `self._sender` here is
   **campaigns'** `HttpSender.send()` (`services/campaigns/app/adapters/peers/__init__.py:388`),
   which posts to `reminders`' `/internal/reminders/send`.
2. Campaigns' own `HttpSender.send()` signature (`peers/__init__.py:388-398`) has **no**
   `button_item_id`/`button_kind` parameters at all, and never will unless someone adds
   them — `dispatch.py` never passes any such value either (grep confirms no
   `button_item_id`/`button_kind` anywhere in `campaigns/`).
3. `CampaignSendIn` (`reminders/app/api/internal.py:726-809`) — the wire model that
   receives that POST — has no `button_item_id`/`button_kind` field either.
4. Therefore `Tick.send_one` (`tick.py:643-662`) never has such a value to forward, and
   never calls `reminders`' `HttpSender.send()` with a non-empty `button_item_id`.

So the `button_item_id`/`button_kind` parameters added to `reminders/app/adapters/
message_sender/__init__.py`'s `HttpSender.send()` and `NullSender.send()` in commit
6eff60f2 are **unreachable from every real caller today** — campaigns (the only
production caller of the flat send path) has no way to populate them, and no other
caller exists. Re-deriving `_card_button_allowed`'s own logic (dispatch.py:284-305)
confirms this isn't a reachable edge case either: that check answers a **carousel
card's** button eligibility (bookings + assistant + AI-on), and it is consumed only as
`carousel_buttons` on the carousel path — never wired to the flat `send()` path's new
parameters.

**Verdict: revert the `button_item_id`/`button_kind` parameters from `HttpSender.send()`
and `NullSender.send()`** (and their `_register_carousel_shown` call inside `send()`).
They are exactly the drift `no-placeholder-drift.md` warns about: a mechanism built
"for later" with no caller and no plan to add one, now that §2 has settled that no
single-item flat send needs a quick-reply button (BOOKING_TYPES get Flow; the other
three get nothing). Keep `send_media()`'s own `button_item_id`/`button_kind` only if §4
below still wants a photo message with a button — see next section.

## 4. `send_media()` needs `flow_token`/`flow_action_data`, not a button — and it has no caller yet either

`send_media()`/`_send_media_sync()` (`message_sender/__init__.py:349-424`) is the
single-item "real photo as header" shape. Grepped: **nothing calls it** outside its own
unit test (`test_send_media.py`) — not `tick.py`, not `dispatch.py`. It is itself
unreached scaffolding right now, independent of the button question.

Given §1's table, the case `send_media()` exists for is: a BOOKING_TYPE campaign with
exactly one covered service/package that has a real photo, on a shop that owns
`feature.bookings` — the natural next step once single-item sends get a header image.
That case wants a **Flow** button, not quick-reply, per the owner's stated preference
and because nothing here is carousel (no Meta restriction applies to a plain send with
an image header, fact #3).

Concrete signature change needed:

```python
async def send_media(self, *, ..., flow_token: str = "",
                     flow_action_data: dict[str, Any] | None = None,
                     button_item_id: str = "", button_kind: str = "service", ...)
```

mirroring `send()`'s own `flow_token`/`flow_action_data` handling verbatim (same
"customer" seed-fill block, same "omit both keys when token is empty" rule). The
`button_item_id`/`button_kind` pair on `send_media()` should be **dropped for the same
reason as §3** — once BOOKING_TYPES use Flow and the other three get nothing, there is
no single-item case left that wants quick-reply.

For `dispatch.py`/`tick.py` to route a single-item BOOKING_TYPE send through
`send_media()` instead of `send()`, `shape.for_send` needs a third outcome alongside
`PLAIN`/carousel/Flow-on-plain-`send`: "Flow-on-`send_media`" when `card_count == 1` and
a photo exists for that one item. That is a real, not-yet-built branch — see §6.

## 5. Full data flow, single-item carousel-eligible campaign, end to end

1. `Dispatcher.fire` (`dispatch.py:181-257`) asks `shape.opens_booking_for` and
   `_card_button_allowed` once per pass, then `shape.for_send` once per recipient
   (card_count from `scope_service_ids`).
2. For 0–1 items on a BOOKING_TYPE with bookings owned: `Shape(flow_token=key,
   flow_action_data={"customer": ""})`. Campaigns' `HttpSender.send()` posts this as
   `flow_token`/`flow_action_data` (and `carousel=False`) to reminders'
   `/internal/reminders/send`.
3. `CampaignSendIn` carries it into the schedule dict `campaign_send` builds
   (`internal.py:833-860`); `Tick.send_one` (`tick.py:414-727`) runs the gate, renders
   the flat template, then calls reminders' own `HttpSender.send(flow_token=...,
   flow_action_data=...)` (`tick.py:643-662`).
4. `HttpSender.send()` (`message_sender/__init__.py:190-347`) resolves the real phone
   number off `subject_ref`, fills `flow_action_data["customer"]` with it, and POSTs
   `/internal/notify` to notification-service with `flow_token`/`flow_action_data` in
   the body.
5. `MetaWhatsApp.send()` (`platform/.../meta.py:29-60`) builds the template's `button`
   component with `sub_type: "flow"` carrying `flow_token`/`flow_action_data`, POSTs to
   Meta's Graph API.
6. Customer receives the approved template with its Flow button, taps it — Meta opens
   the WhatsApp Flow directly; no webhook to whatsapp-assistant is involved in *opening*
   it (unlike a carousel tap).
7. The Flow's own screens call `notification-service`'s `/internal/whatsapp-flow/booking`
   route (single HTTP endpoint, four ops: options/calendar/slots/reserve —
   `flow_booking_backend.py:1-12`), which dispatches into whatsapp-assistant's
   `FlowBookingBackend`, which calls the same `assignment.py` engine
   `RealBookingProvider` (the AI channel) also calls. One booking engine, two doors.
8. `reserve` writes the booking; loyalty redemption, if any, rides the same call
   (`flow_booking_backend.py:33-44`).

(The carousel-tap path is a *different* end-to-end flow — Meta webhook →
notification-service → whatsapp-assistant's `handle_button_reply` →
`_handle_carousel_pick` → `_availability_for` → `_propose_slot`, confirmed
deterministic and already correctly wired per commit history; nothing here changes it.)

## 6a. Closing the Meta carousel-button gap: a Flow bridge from a carousel tap

**Yes, this is technically real and buildable — not blocked by Meta's carousel rule at
all, but not free either.** Traced concretely:

- `HttpSender.send_flow()` (`reminders/.../message_sender/__init__.py:426-477`) already
  posts `{"type": "flow", "flow_token", "flow_id", "flow_cta", "flow_screen",
  "flow_data", ...}` to a configured `NOTIFICATION_INTERACTIVE_SEND_PATH`. Its own
  docstring is explicit: this is "a Flow sent as a bare interactive message with **no
  template** behind it at all" — a **separate message**, not a component of any
  template. It is dead code today only because nothing calls it, not because it can't
  work.
- `platform`'s `InteractiveNotifyIn`/`internal_notify_interactive` (`notification-
  service/app/api/internal.py:178-236`) confirms the same shape: `type: Literal["button",
  "list", "flow", "location_request"]`, and the route's own docstring says it all "goes
  through the SAME audited... path" and is "sent inside the 24h customer-service window
  (no template needed)" (line 215, describing the sibling `button`/`list` types — `flow`
  shares the same envelope and window rule, confirmed by `build_flow`'s own docstring
  never mentioning a template at all, only Meta's Flow-message spec). **A carousel tap is
  itself an inbound customer message, which opens/refreshes that 24h window** — so a
  follow-up Flow send immediately after the tap is squarely inside it. This confirms the
  owner's instinct: Meta's carousel-button restriction governs only what a card's own
  button may be (`quick_reply`/`url`); it says nothing about what the bot may send
  *after* receiving that tap as an ordinary inbound event. The bridge is not blocked.
- **The real gap is on whatsapp-assistant's own side, in two places:**
  1. Its outbound adapter, `InteractiveNotifySender` (`whatsapp-assistant/app/adapters/
     whatsapp_sender/direct.py:48-127`), implements `send_interactive` and `send_list`
     only. There is **no `send_flow` method** — the class that would call
     notification-service's `type: "flow"` branch simply does not exist yet on this
     side, mirroring `ReplyPlan.kind` (`conversation.py:499`), which is typed
     `"text" | "interactive" | "list" | "carousel" | "none"` — **no `"flow"` kind
     either.** Both need a new case.
  2. `_handle_carousel_pick` (`conversation.py:1547-1579`) always proceeds by calling
     `_propose_slot`, which drives the deterministic chat-based propose/confirm tool.
     There is no branch that instead mints a `flow_token` and returns a
     `ReplyPlan(kind="flow", ...)` for the caller to dispatch through the new sender
     method. This is a straightforward addition in the same spirit as the existing
     single-slot vs. multi-slot branch already there.
- **A third, subtler gap: pre-selecting the item.** The whole point of the bridge is
  that the customer already told us which service/package by tapping that specific
  card — the Flow must open **already on that item**, not re-ask "which service?".
  `FlowBookingBackend.options(dimension="service", ...)` (`flow_booking_backend.py:
  134-139`) unconditionally returns the **full active catalog** with no code path to
  skip or pre-fill this step — unlike the `staff` dimension, which already has a
  documented "skip itself" contract (v0.18.53) for exactly this kind of conditional
  step. `flow_action_data`/the Flow's seed data today carries only `CUSTOMER_SEED`
  (`core/shape.py:65-67`) — no service/package key exists to seed. Making the bridge
  give the "same premium experience" (skip straight to the calendar) requires: (a) the
  Flow's own screen definition (platform-side JSON, outside this repo's services) to
  accept a seeded default/pre-selection for the service step, and (b) teaching
  `FlowBookingBackend`/its screen-skip logic to honor it — the same shape of change
  v0.18.53 already made for `staff`. Without this, the bridge still works, but opens the
  Flow at "pick a service" instead of straight at "pick a time" — a real but lesser
  version of "the same premium experience."

**Verdict on chat-based propose/confirm vs. this bridge:** do NOT rip out the chat-based
path — it must remain the fallback (deployments/tenants where `flow_id`/`flow_name` for
booking is not configured, or the pre-selection work in the previous paragraph is not
yet done). Once built, the bridge should become the PREFERRED outcome of a carousel tap
on a shop that owns `feature.bookings` and has the Flow provisioned, with chat propose/
confirm remaining the answer for a shop that does not — same fail-to-plain-and-safe
posture this whole design already follows everywhere else (`shape.py`'s "NO is today's
message, byte for byte").

## 6. Revised next steps, one committed slice at a time

1. **Revert** `button_item_id`/`button_kind` from `reminders`' `HttpSender.send()` and
   `NullSender.send()` (§3) — dead parameters, no caller, no plan to add one.
2. **Add** `flow_token`/`flow_action_data` to `send_media()`/`_send_media_sync()`
   (§4), mirroring `send()`'s existing handling exactly (including the `"customer"`
   fill and the "omit when empty" rule). Do **not** add `button_item_id`/`button_kind`
   there.
3. **Extend `shape.for_send`** with the one real new branch: `card_count == 1` on a
   BOOKING_TYPE with bookings owned *and* that single item has an uploaded photo →
   signal "Flow via `send_media`" rather than "Flow via `send`". This needs a way for
   `shape.py` to know a photo exists without duplicating reminders' own catalogue-image
   lookup — likely a boolean campaigns already has or can cheaply get from its audience
   read; needs its own small design pass, not assumed here.
4. **Wire `tick.py`'s `send_one`** to call `send_media()` instead of `send()` when the
   row says so, passing the same `flow_token`/`flow_action_data` fields through.
5. **No changes needed** to `mkt_announcement`/`awr_care_tip`/`mkt_loyalty_activation` —
   confirmed correct as-is (§2). Do not add a Flow or a button to their single-item case.
6. **No changes needed** to the carousel path — Meta's restriction is absolute, the
   quick-reply mechanism there is already correct and separately audited.
7. When `platform` is repinned past `v0.22.5`, re-check that `header_media_id`/
   `button_payload` landing on `/internal/notify`'s `NotifyIn` don't reintroduce the
   quick-reply button this design just removed — that peer capability existing is not,
   by itself, a reason to re-add `button_item_id` to `reminders`' senders.
8. **The carousel→Flow bridge (§6a), as its own separate slice, after the above:**
   (a) add `send_flow`/`kind="flow"` to whatsapp-assistant's `InteractiveNotifySender`/
   `ReplyPlan`; (b) branch `_handle_carousel_pick` to use it when the shop's booking
   Flow is configured, falling back to today's chat propose/confirm otherwise; (c) only
   then take on the harder pre-selection work (Flow screen seed + `FlowBookingBackend`
   skip logic) — ship (a)+(b) first even without pre-selection, since "opens the native
   Flow starting one step later" is still strictly better than the chat-only path it
   replaces, and is independently testable before the fuller premium version lands.
