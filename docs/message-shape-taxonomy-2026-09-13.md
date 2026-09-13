# A shape-based classification for every outbound WhatsApp message

This replaces goal/class naming (`services/campaigns/app/core/models.py`'s `GOAL_TEMPLATE`,
`services/campaigns/app/core/goals.py`'s `CARDS`) as the thing that decides SEND SHAPE. Those
stay exactly as they are for CONTENT — which wording, which goal, which Meta `category`
(`UTILITY`/`MARKETING`/`AUTHENTICATION`). This document adds one new, orthogonal axis:
**what kind of thing this message structurally is**, independent of what it says.

## 0. Why the current system can't answer "what shape is this"

`GOAL_TEMPLATE` (`models.py:42-66`) maps a goal to a `(template_type, class)` pair — content
metadata only. Shape is derived separately and ad hoc: `services/campaigns/app/core/shape.py`
hand-lists `BOOKING_TYPES = frozenset({"mkt_winback", "mkt_personal_occasion", "mkt_offer"})`
(line 47) and `CAROUSEL_TYPES = BOOKING_TYPES | {"mkt_loyalty_activation", "mkt_announcement",
"awr_care_tip"}` (lines 62-63) — two frozensets of template-type strings that must be kept in
sync by hand every time a template is added, and that only cover the six marketing/awareness
types campaigns itself sends. `services/reminders/app/core/tick.py` separately special-cases
`row.get("carousel")` (`tick.py:572-592`) and a `kind == "rating_request"` check for whether to
attach `flow_token` (`tick.py:1016-1022`) — a second, independent place where "does this
message act like X" is re-derived from context rather than declared. Neither file has ever
heard of `wa_catalog_carousel` (whatsapp-assistant's own carousel) or the three
whatsapp-assistant trigger templates (`renewal_trigger.py`, `wallet_low_balance_trigger.py`,
`visit_trigger.py`'s staff-menu reply) — those are sent through an entirely separate,
imitative sender trio (`app/adapters/whatsapp_sender/{template,direct,carousel}.py`) that
re-implements the same shape logic a third time, undocumented and unsynchronized with either
of the other two. Adding template #1001 today means finding all three places and hoping you
didn't miss one.

## 1. Full inventory — every distinct sending path

One row per real distinct path (a warm/feminine pair is one row). Columns: purpose, trigger,
current shape, actionable-and-how.

| # | Path (name/type) | Purpose | Triggered by | Current shape | Actionable |
|---|---|---|---|---|---|
| 1 | `svc_visit_confirmation` | Confirm a walk-in visit was logged | reminders, 10 min after a visit (`tick.py` scheduled path) | plain text | No |
| 2 | `svc_visit_confirmation_rating` | Same, + ask for a rating | reminders, same trigger, shop owns `feature.rating` | plain text + Flow button (`rating_flow`) | Yes — native Flow popup |
| 3 | `svc_visit_redeemed` | Confirm a visit that included a loyalty redemption | reminders, visit event | plain text | No |
| 4 | `svc_booking_confirmation` | Confirm a booking was made | reminders, booking event | plain text | No |
| 5 | `svc_follow_up` | "How was it" check-in, cyclic shops | reminders, scheduled (`deferral: defer`) | plain text | No |
| 6 | `svc_service_reminder` | "Your cycle is due" nudge | reminders, scheduled | plain text | No |
| 7 | `svc_receipt` | Amount receipt | reminders, visit event | plain text | No |
| 8 | `per_account_notice` | Points-balance change notice (never opted out) | loyalty, via reminders' gate | plain text | No |
| 9 | `per_points_expiring` | Points about to expire (never opted out) | loyalty, scheduled | plain text | No |
| 10 | `per_dsar_code` | Data-request OTP code | operations, on demand | plain text | No |
| 11 | `awr_care_tip` (flat) | Care/usage tip | campaigns, `awareness` goal | plain text | No |
| 12 | `awr_care_tip` (carousel, **inactive**) | Same, multi-item pick | campaigns, `awareness` goal, ≥2 items | carousel, 3 cards, quick-reply | Yes — chat continuation |
| 13 | `wrn_safety_notice` | Safety/recall notice | operations, on demand | plain text + **text** header ("تنبيه") | No |
| 14 | `mkt_offer` (flat) | Discount offer | campaigns, `service_offer`/`package_offer` goal, ≤1 item | plain text + Flow button (`booking_flow`), only if shop owns `feature.bookings` | Yes — native Flow, when licensed |
| 15 | `mkt_offer` (carousel, **inactive**) | Same, ≥2 items | campaigns, same goal, ≥2 items | carousel, 3 cards, quick-reply | Yes — chat continuation |
| 16 | `mkt_winback` (flat) | Win back an absent customer | campaigns, `win_back` goal, standing | plain text + Flow button, licensed | Yes |
| 17 | `mkt_winback` (carousel, **inactive**) | Same, ≥2 items | campaigns | carousel | Yes — chat continuation |
| 18 | `mkt_loyalty_activation` (flat) | "You're close to a reward" | campaigns, `reward_loyal` goal, standing | plain text, **no button at all** | No |
| 19 | `mkt_loyalty_activation` (carousel, **inactive**) | Same, ≥2 rewards | campaigns | carousel, quick-reply "استبدل الآن" | Yes — chat continuation |
| 20 | `mkt_announcement` (flat) | "We have something new" | campaigns, `announce` goal, manual | plain text, **no button at all** | No |
| 21 | `mkt_announcement` (carousel, **inactive**) | Same, ≥2 items | campaigns | carousel, quick-reply "احجز الآن" | Yes — chat continuation |
| 22 | `mkt_personal_occasion` (flat) | Birthday/occasion discount | campaigns, `occasion` goal, scheduled | plain text + Flow button, licensed | Yes |
| 23 | `mkt_personal_occasion` (carousel, **inactive**) | Same, ≥2 items | campaigns | carousel | Yes — chat continuation |
| 24 | `per_weekly_digest` | Owner's weekly report | insights (`app/api/internal.py:288-299`, via reminders' `/internal/reminders/send`) | plain text + Flow button (`report_flow`) | Yes — native Flow |
| 25 | `wa_catalog_carousel` | Standalone service catalogue | whatsapp-assistant, AI-tool-triggered (`app/core/tools.py`), its **own** `CarouselSender` — not reminders' `message_sender` | carousel, 5 cards, quick-reply "احجز الآن" | Yes — chat continuation |
| 26 | AI renewal reminder | Subscription/wallet renewal nudge | whatsapp-assistant `renewal_trigger.py:73-76`, own `TemplateSender` | plain text + Flow token (`renew:{invoice_id}`) | Yes — native Flow |
| 27 | AI low-balance notice | Wallet balance warning | whatsapp-assistant `wallet_low_balance_trigger.py:60-62` | plain text, template `ai_wallet_low_balance` | Unconfirmed — no flow_token cited at the call site; **flag as edge case #3** below |
| 28 | AI staff-menu reply | Internal staff menu message | whatsapp-assistant `visit_trigger.py:113-115` | template send via `send_template` | Likely button/list, not in `templates.seed.json` — **flag as edge case #4** |
| 29 | Bare interactive send (`send_flow`) | A Flow with **no template at all**, inside the 24h session window | reminders' `HttpSender.send_flow` (`message_sender/__init__.py:426-477`) — **unused today**, no caller | interactive message, no template | Yes — native Flow, no template needed |
| 30 | AI interactive button/list | In-chat quick actions | whatsapp-assistant `direct.py`'s `InteractiveNotifySender` | interactive message, no template | Yes — chat continuation |

Sources: full read of `services/operations/data/templates.seed.json` (2417 lines), full read of
`services/reminders/app/core/tick.py`, `.../message_sender/__init__.py`, `services/campaigns/
app/core/{models,goals,shape}.py`, `services/insights/app/api/internal.py` +
`app/adapters/peers/__init__.py`, and `services/whatsapp-assistant/app/adapters/
whatsapp_sender/{carousel,direct,template}.py` + its three trigger files. `services/loyalty`
and `services/bookings` were grepped and confirmed to send nothing directly — loyalty routes
everything through reminders' gate (`app/adapters/peers/__init__.py:1-9`, its own docstring:
"there is no loyalty-shaped shortcut to notification-service"), and bookings has zero hits for
`message_sender|HttpSender|send_carousel|send_media|notify`.

## 2. The four new shape categories

Named for structure, not purpose. None reuse `service`/`personal`/`marketing`/`awareness`/
`warning` (today's `class`) or `win_back`/`reward_loyal`/… (today's goal names).

### NOTICE — says something, asks for nothing
**Contract:** exactly one text body, optional plain-TEXT header only (never IMAGE/VIDEO), no
button of any kind, no `flow_button`, no `carousel` key. Meta `category` may be `UTILITY` or
`MARKETING` — that's content, not shape.
**Send path:** `HttpSender.send()` in `services/reminders/app/adapters/message_sender/
__init__.py` (lines 190-347), called with `flow_token`/`button_payload` both empty. Every row
lands here unconditionally — no per-type branch needed inside `send()` itself.

### INVITE — opens exactly one thing outside the chat, OR hands one specific item to the bot
**Contract:** single item (0 or 1), optional media header, exactly one button. The button is one
of THREE kinds, not two — **revised 2026-09-13 per the owner's own instruction**: a WhatsApp Flow
(native popup), a URL (external link), or a quick-reply that hands the ONE named service/package
to the bot's own booking conversation (`carousel:{kind}:{id}`, the exact mechanism GALLERY's
per-card button already uses). No `carousel` key regardless of which button kind.

The quick-reply variant is what makes a single-item `mkt_announcement`/`awr_care_tip`/
`mkt_loyalty_activation` actionable when the owner attached exactly one service/package to it — a
new announcement about ONE specific service should let the customer book it, the same way a
multi-item announcement's carousel card already does. These three types are NOT "no button,
forever" as an earlier pass concluded — they are button-LESS only when nothing bookable is
attached (a pure informational text), and INVITE (quick-reply variant) the moment one is.
**Send path:** `send()` when there's no media header, `send_media()` (lines 349-424) when there
is. Flow/URL variants set `flow_token`/`flow_action_data` (or a template's own URL button, no
extra field); the quick-reply variant sets `button_item_id`/`button_kind` — the parameters added
to `HttpSender.send()`/`NullSender.send()` in commit `6eff60f2`, KEPT (an earlier pass called
them dead code and recommended reverting them — superseded by this decision; they are the
correct, already-built mechanism for this variant, not a mistake to undo).

### GALLERY — a swipeable set of 2-10 items
**Contract:** `carousel` object with 2-10 cards (Meta's own hard bound,
`notification-service/app/core/whatsapp_templates.py:97`, `_CAROUSEL_MIN, _CAROUSEL_MAX = 2,
10`), each card an `IMAGE`/`VIDEO` header (`_CARD_HEADER_FORMATS`, line 98) with exactly one
`QUICK_REPLY` or `URL` button (`_CARD_BUTTON_TYPES`, line 99) — Meta forbids `flow` as a
carousel-card button sub-type entirely (`whatsapp_carousel.py:18`, `_BUTTON_SUB_TYPES =
("quick_reply", "url")`), so GALLERY can never open a native Flow; a tap always continues in
chat.
**Send path:** `send_carousel()` (lines 532-645) unconditionally.

### PROMPT — an interactive message with no template behind it
**Contract:** no approved WhatsApp template at all; sent inside the 24-hour customer-service
session window, opened by an inbound event (a reply, a carousel tap). Payload is `button`,
`list`, or `flow`.
**Send path:** reminders' `send_flow()` (lines 426-477, currently dead — no caller anywhere in
`tick.py`) and whatsapp-assistant's own `InteractiveNotifySender` (`direct.py`). This is the one
category two independent implementations already exist for and neither talks to the other
— named explicitly as edge case #1 below.

## 3. Mapping every inventoried row

| Row | Category |
|---|---|
| 1 confirmation, 3 redeemed, 4 booking, 5 follow-up, 6 cycle reminder, 7 receipt, 8 account notice, 9 points expiring, 10 DSAR code, 11 care tip (flat), 13 safety notice, 18 loyalty activation (flat), 20 announcement (flat) | **NOTICE** |
| 2 visit+rating, 14/16/22 offer/winback/occasion (flat, licensed), 24 weekly digest, 26 AI renewal | **INVITE** |
| 12/15/17/19/21/23 all six carousel variants (currently inactive), 25 `wa_catalog_carousel` (active) | **GALLERY** |
| 29 `send_flow`, 30 AI interactive button/list | **PROMPT** |

Edge cases, named rather than papered over:

1. **Two live implementations of GALLERY.** `send_carousel()` in reminders and
   whatsapp-assistant's `app/adapters/whatsapp_sender/carousel.py`'s `CarouselSender` do the
   same job (the latter's own module docstring: "Imitates services/reminders/…HttpSender
   exactly") but are separate code, unaware of each other. A shape-category field only pays off
   fully once both read it from one place — see §5.
2. **`wrn_safety_notice`'s TEXT header.** NOTICE's contract must allow an optional plain-text
   header (not just "no header ever") — this row is the only one that uses it. It changes
   nothing about the send path (`send()` doesn't care whether a text header is present), so it
   stays NOTICE rather than forcing a fifth category.
3. **Row 27, AI low-balance notice.** The trigger site (`wallet_low_balance_trigger.py:60-62`)
   was not confirmed to carry a `flow_token`. If it doesn't, it's NOTICE; if a future button is
   added, it moves to INVITE. Flagged rather than assumed either way — the template itself
   (`ai_wallet_low_balance`) isn't in `templates.seed.json`, meaning platform-tenant/AI
   templates live in a separate registry this document didn't fully trace.
4. **Row 28, AI staff-menu reply.** Same gap — not present in the seed file inventoried, likely
   a `button`/`list` PROMPT rather than an approved template; needs its own confirmation before
   being formally categorized.
5. **`send_media()` and `send_flow()` are both currently uncalled.** Their contracts are
   real (INVITE's media variant, PROMPT's template-less variant) but no production code path
   reaches them yet in reminders — see the existing `docs/carousel-booking-button-design-
   2026-09-13.md` (§4, §6a) for the concrete next steps to wire them up. This taxonomy doesn't
   change that work, it gives it a name: closing those two gaps is "make INVITE's media form
   and PROMPT's reminders-side form reachable," not two unrelated fixes.

## 4. Data-model change

Add one new field to every row in `services/operations/data/templates.seed.json`:
`"shape_category": "NOTICE" | "INVITE" | "GALLERY" | "PROMPT"`. This is the single field a new
template declares — an operator adding row #1001 picks one of four values, done. It sits beside
`class`/`category` (content/regulatory, unchanged) and beside `header`/`button`/`flow_button`/
`carousel` (which stay as the literal Meta-facing fields the category constrains, not
duplicated data — `shape_category` is the *declaration*, those are the *fields it requires*).
A lightweight validator (extending `ci/check_meta_rules.py`, which already checks this file)
should enforce the contract per category: NOTICE forbids `button`/`flow_button`/`carousel`;
INVITE requires exactly one of `flow_button` or a URL button and forbids `carousel`; GALLERY
requires `carousel` with 2-10 cards; PROMPT has no row in this file at all (it never has an
approved template).

Reading side:
- `services/campaigns/app/core/shape.py`: delete `BOOKING_TYPES`/`CAROUSEL_TYPES`
  (lines 47, 62-63) and the branching in `for_send()` (lines 110-133). Replace with one lookup
  — resolve the template's `shape_category` (via operations' template read, the same source
  `goals.py:cards()` already calls for `fills_by_type`) and switch on it: `GALLERY` + card_count
  `>=2` → `Shape(carousel=True)`; `INVITE` + `opens_booking_for()` → `Shape(flow_token=...)`;
  everything else → `PLAIN`. `opens_booking_for()` (line 95) keeps its licence check, now gated
  by category membership instead of a hand-listed set.
- `services/reminders/app/core/tick.py`: `send_one` (lines 572-662) currently branches on
  `row.get("carousel")` then falls through to `send()`. Branch on `shape_category` instead:
  `GALLERY` → `send_carousel()`, `INVITE` with media → `send_media()`, `INVITE` without media or
  `NOTICE` → `send()`. The `kind == "rating_request"` special case (lines 1016-1022) becomes
  unnecessary — `svc_visit_confirmation_rating`'s row already says `INVITE`.
- whatsapp-assistant's trigger files and its own `CarouselSender`/`TemplateSender` should read
  the same `shape_category` field for their templates too, closing edge case #1 — the category
  becomes the one place send-shape is decided, for every service, not just reminders'.

## 5. Growth check — three plausible future templates

1. **Subscription-renewal reminder** (a single text nudging the shop owner to renew, with a
   Flow that opens the renewal/payment screen). One item, one Flow button → **INVITE**,
   no new category — this is structurally identical to row 26 (AI renewal), which already
   exists and already fits.
2. **Staff-invite message** (a single text inviting a new staff member, with a button that
   opens an external invite link rather than a native Flow). One item, one button, but a
   `URL` sub-type rather than `flow` — this is exactly why INVITE's contract in §2 says "Flow
   **or** URL," not "Flow only": both are "leaves the chat to open one specific thing," the
   structural fact that matters, versus a quick-reply, which stays in chat. Lands in
   **INVITE** without inventing anything.
3. **Multi-item cart-abandonment nudge** (2-5 abandoned services/packages, each shown with its
   own photo and a "book this" quick-reply). Multiple items, quick-reply continuation →
   **GALLERY**, identical in shape to today's `mkt_offer` carousel variant (row 15) — content
   differs (a cart, not a discount), shape doesn't.

No future case needed a fifth category; the two structural questions that matter — "1 item or a
2-10 set?" and, if actionable, "opens something outside the chat, or continues in chat?" —
already partition every message this product sends today and, by these three tests, plausibly
sends next.
