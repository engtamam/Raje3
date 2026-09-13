# A single-item bot tool: photo + text + button, wired into real booking

Builds directly on `docs/carousel-booking-button-design-2026-09-13.md` and
`docs/message-shape-taxonomy-2026-09-13.md` (INVITE's quick-reply variant, kept per the
owner's instruction). Every claim below cites `file:line` in this checkout of
`services/whatsapp-assistant`.

## 1. Confirmed: the live gap

`suggest_services_carousel` (`app/core/tools.py:403-416`) is the bot's only
catalog-presenting tool. It fetches candidates, filters to those with a real
`image_url`, caps at `max_carousel_cards`, then:

```python
with_images = [c for c in cards if c.image_url][:max_carousel_cards]
if len(with_images) < 2:
    return "ما عندي صور كافية حالياً أعرضها لك — بس أقدر أخبرك عن خدماتنا بالتفصيل."
return RenderedCarousel(cards=with_images)
```

(`tools.py:413-416`). This confirms the suspected bug precisely, and rules out the
*other* half of the suspicion: it never reaches `CarouselSender` with one card, so
`CarouselSender`'s own "fewer than two cards raises `SendFailed`" floor
(`app/adapters/whatsapp_sender/carousel.py`, module docstring and
`_send_carousel_sync`'s `if len(built) < 2: raise SendFailed(...)`) is never hit by
this path — the gate above it already turns back a single candidate before any send is
attempted. So it is not a crash. **It is a silent downgrade**: a shop with exactly one
real, photographed service gets a flat apology text — "not enough photos" — even though
it has exactly the photo needed to show one great card. This is the concrete gap
task item #3 asked to confirm. `RenderedCarousel` itself (`tools.py:108-112`, its own
docstring: "`cards` already carries only items with a real image_url") and
`ReplyPlan.carousel` (`conversation.py:499,505-506`) both assume ≥2 by construction
today — there is no third value between "text" and "carousel" for exactly one card with
a photo.

Also confirmed and ruled out for reuse: `catalog_provider.py`'s own module docstring
says the port was "built ahead of any consumer," but that is stale — `tools.py:408`
already calls `catalog_provider.list_cards`, so the port has a live production
consumer today (worth a one-line docstring fix when this ships, not scope of this
design).

## 2. The new tool: `offer_service_card`

One new allowlisted tool, added beside `suggest_services_carousel` in
`app/core/tools.py` and to `LLM_TOOL_ALLOWLIST` (`app/config.py`):

```
offer_service_card(kind: "service" | "package" = "service", hint: str = "")
```

`hint` is optional free text the model may pass ("الحلاقة", "باقة العرايس") to bias
which single item is chosen when several plausible candidates exist and only one
should be shown — same posture as `suggest_related_service`'s existing arguments,
never a raw id the model invents. Behavior:

1. Read-only, same posture as `suggest_services_carousel` — no `PendingProposal`,
   nothing state-changing yet.
2. Resolve one candidate through `catalog_provider.list_cards` (reusing the exact same
   read the carousel tool already makes — no new port method needed) filtered to
   `image_url != ""`, picked by `hint` match if given, else the first.
3. If zero candidates with a photo exist: return the same "no photos available" text
   `suggest_services_carousel` already returns — this failure mode is unchanged,
   correctly, since there is genuinely nothing to show.
4. If ≥1 candidate exists: return a new **`RenderedSingleCard`** value object —

```python
@dataclass(frozen=True)
class RenderedSingleCard:
    """One CatalogCard, photo + text + one button — the INVITE/quick-reply shape.
    Never a PendingProposal: identical posture to RenderedCarousel, a single card is
    still presentational, the state-changing action is still gated behind the button
    tap, never this tool call."""
    card: CatalogCard
```

## 3. Reused, not reinvented: the reply-id shape

**Recommendation: reuse `"carousel:{kind}:{item_id}"` verbatim, zero changes to
`_handle_button_reply_locked`/`_handle_carousel_pick`.** This is the simplest correct
answer and the one the existing architecture already begs for:

- `CarouselSender._send_carousel_sync` already builds each card's button payload as
  exactly this string (`carousel.py`: `f"carousel:{c.kind}:{c.id}"`).
- `_handle_carousel_pick` (`conversation.py:1547-1579`) only checks two things: the
  `reply_id` prefix, and `item_id in conv.shown_carousel_ids` (`conversation.py:1563`).
  Nothing in it assumes "≥2 cards were shown" — it reads a single `(kind, item_id)`
  pair regardless of how many cards preceded it.
- The one piece that must be threaded through is `conv.shown_carousel_ids`. Today it is
  only populated in the `RenderedCarousel` branch (`conversation.py:1479`,
  `conv.shown_carousel_ids = [c.id for c in result.cards]`). A `RenderedSingleCard`
  branch needs the identical line with a one-element list:
  `conv.shown_carousel_ids = [result.card.id]`. Same binding rule, same anti-forgery
  property (§ from the carousel design doc: "fixed against exactly this session's own
  render"), applied to a set of size one instead of size ≥2. The name
  `shown_carousel_ids` stays accurate in spirit even for one card — no rename needed
  for this slice; a future cleanup could rename it to `shown_card_ids` but that is
  cosmetic, not correctness-bearing.

Net result: **`_handle_carousel_pick`/`_handle_slot_pick`/`handle_button_reply` need
ZERO code changes.** The single-item tap resolves through the exact same
`_availability_for` → `_propose_slot` deterministic path a carousel tap already uses,
because it produces the same `reply_id` shape and the same binding set. This is the
one design choice that makes the whole feature "wiring," not "a parallel mechanism."

## 4. Where `conversation.py`'s dispatch branch goes

`_route_to_llm`'s existing branch structure (`conversation.py:1466-1494`) gains one
new `isinstance` arm, inserted between the `RenderedProposal` and `RenderedCarousel`
checks (order doesn't matter functionally, but single-before-carousel reads naturally
as "fewer items, simpler shape, checked first"):

```python
if isinstance(result, T.RenderedSingleCard):
    conv.shown_carousel_ids = [result.card.id]
    conv.raw_window.append({"role": "assistant", "text": "[بطاقة خدمة]", "at": now})
    conv.state = "idle"
    conv.session_closed_at = now
    conv.batch_deadline = 0
    await self._save(conv)
    return ReplyPlan(kind="card", card=result)
```

`ReplyPlan` (`conversation.py:496-506`) gains one field, `card:
T.RenderedSingleCard | None = None`, and its `kind` comment extends to `"text" |
"interactive" | "list" | "carousel" | "card" | "none"`. A dedicated `"card"` kind
(rather than overloading `"carousel"` with a length-1 list) keeps the sender
dispatch in the API layer (`app/api/internal.py`, wherever `ReplyPlan.kind` is
switched on to pick which `WhatsAppSender` method to call) an explicit, readable
one-to-one match with the two adapter methods in §5, rather than an implicit
"carousel of one" special case downstream.

## 5. New sender code: one method, not a new class

**Recommendation: add `send_single_card` to the existing `CarouselSender`/
`NullCarouselSender` pair in `app/adapters/whatsapp_sender/carousel.py`, not a new
adapter class.** Reasoning: the entire fetch-photo → upload-media → build-button
sequence is identical to one iteration of `_send_carousel_sync`'s per-card loop
(`carousel.py`'s `_fetch_image`/`_upload_media_id`, already private helpers on this
class) — the only difference is the final POST target and body shape (one card
inline in an ordinary interactive/template send, not a `cards` array to
`/internal/notify/whatsapp/carousel`). Duplicating those two HTTP helpers into a new
class would be exactly the drift the carousel adapter's own docstring already warns
against ("imitates X exactly" — imitate this file, don't re-derive it).

```python
async def send_single_card(self, *, tenant: str, to: str, card: CatalogCard,
                           idempotency_key: str) -> str:
    """Photo + text + ONE quick-reply button, direct to notification-service — the
    INVITE-quick-reply shape (docs/message-shape-taxonomy-2026-09-13.md §2). Reuses
    this class's own _fetch_image/_upload_media_id exactly as _send_carousel_sync
    does per card; posts to notification-service's ordinary single-interactive-media
    route (NOT reminders' send_media(), which is template-keyed, subject_ref-resolved,
    and reminders-only — this service resolves `to` itself, from the live
    conversation, and must speak to notification-service directly like every other
    sender in this package)."""
    return await asyncio.to_thread(self._send_single_card_sync, tenant=tenant, to=to,
                                   card=card, idempotency_key=idempotency_key)
```

The sync half fetches/uploads the one image (reusing `_fetch_image`/
`_upload_media_id` unchanged), then POSTs a body shaped like
`InteractiveNotifySender.send_interactive`'s payload (`direct.py:60-70`) but with an
`IMAGE` header (`media_id`) added and a single `quick_reply` button carrying
`carousel:{kind}:{id}` — i.e., structurally the INVITE category's media form from the
taxonomy doc, sent through this service's own notification-service posture (never
through reminders, confirmed unreachable/wrong-shaped for the bot in §6).

`container.py` needs no new wiring beyond exposing this one extra method on the
object it already builds as `catalog_provider`'s sibling sender — same
`CarouselSender` instance the carousel tool already uses.

## 6. Why NOT reminders' `send_media()`

Traced concretely (`services/reminders/app/adapters/message_sender/__init__.py:349-424`):

- It is **template-keyed** (`template_key` in the payload, `_send_media_sync`'s
  `payload["template_key"] = template_name"`, needing an approved Meta template row)
  — the bot's carousel/interactive sends are deliberately template-free where
  possible (`InteractiveNotifySender`, `direct.py`'s own docstring: "an interactive
  shape... instead of calling Meta's Graph API directly").
- It resolves the recipient via `self._recipient(tenant, subject_ref)` — reminders'
  own contacts/subject_ref machinery. The bot never has a `subject_ref` for a live
  chat; it holds a real phone number for the length of the conversation
  (`template.py`'s own docstring: "`to` here is a real phone number the CALLER
  already holds... This service never persists a phone number at rest").
- Its `button_item_id`/`button_kind` → `button_payload` (lines 405-406) is exactly
  the mechanism the taxonomy doc's INVITE section describes for **campaigns'**
  single-item sends — a different caller, a different transport
  (`/internal/notify` via reminders), a different lifecycle (works outside any open
  session, needs a template). It is real, already-shipped code for that caller, and
  it is **not reusable by the bot** — confirmed, not assumed, by the two structural
  mismatches above.

**Verdict: the bot needs its own method (§5), mirroring the shape of
`send_media()`'s photo-fetch/upload/send flow but posted through this package's own
posture, exactly as `CarouselSender`'s own docstring already frames its relationship
to reminders' `HttpSender` ("imitates... exactly" — the pattern to copy, not the code
to call).**

## 7. The automatic fallback rule — one rule, not two tools bolted together

**Recommendation: `offer_service_card` is never called directly by the model as a
distinct intent from "show me options." Instead, `suggest_services_carousel` becomes
the single entry point, and its own candidate-count branch is extended:**

```
count == 0 photographed candidates → "no photos" text (unchanged)
count == 1 photographed candidate  → RenderedSingleCard  (NEW)
count >= 2 photographed candidates → RenderedCarousel     (unchanged)
```

This replaces the `len(with_images) < 2` early-return in `tools.py:414-415` with a
`== 1` branch returning `RenderedSingleCard(card=with_images[0])`, keeping `== 0` as
the only remaining "sorry" text. This is the "automatic fallback... one tool-selection
rule, not a special case bolted on" the task asked for: there is still exactly one
tool the model calls to browse the catalog; the shape returned is chosen by real
candidate count, the same "the model proposes, the code decides the real shape"
posture `tools.py`'s own module docstring establishes for the whole file. A second,
separate `offer_service_card` tool the model must itself choose between would
reintroduce a model-judgment call ("is 1 the right count to show one card?") exactly
where the architecture's whole point is never trusting the model with that judgment.

Given this, §2's standalone `offer_service_card(kind, hint)` tool schema is not
needed as a *model-facing* tool at all — it becomes an internal helper function
`_render_single_or_carousel(cards)` called from inside `suggest_services_carousel`'s
existing body, callable by any future tool that also needs "show what we've got,
sized correctly," but with only one allowlisted, model-facing tool. This is simpler
than the initial framing in §2 and is the recommended final shape — noted explicitly
since it revises this document's own earlier section rather than leaving both as if
equally live.

## 8. Should the bot's carousel switch to the template-free "interactive media
carousel"?

**Recommendation: not in this slice — defer, revisit only if template-approval
friction actually bites.** Reasoning:

- The bot's carousel already avoids Meta template *registration* friction for its
  general interactive sends (`InteractiveNotifySender` exists precisely to skip
  templates for button/list). But `wa_catalog_carousel`
  (`app/config.py:490`, `WHATSAPP_CATALOG_CAROUSEL_TEMPLATE_NAME`) is still
  template-based today, and switching it to the template-free `type: "interactive"`
  carousel shape would indeed drop the one remaining template dependency for this
  specific send.
- However: `CarouselSender`'s whole design already treats the carousel POST as an
  opaque call to a notification-service route (`/internal/notify/whatsapp/carousel`)
  that "already exists and is already used by other carousel senders on the
  platform" (its own docstring). Changing the wire shape from template-based to
  template-free interactive is a **notification-service-side** change (which route,
  which body shape it expects), not something this repo's adapter alone can decide —
  it would need to be coordinated with whatever else calls that same route
  (reminders' own `send_carousel`, per the taxonomy doc's edge case #1: "two live
  implementations of GALLERY... unaware of each other"). Doing it for the bot alone,
  ahead of that shared decision, would create a **third**, differently-shaped
  carousel implementation rather than closing the two that already exist — worse,
  not better, for the exact problem edge case #1 already names.
- Net: the single-item tool in this design (§§2-7) delivers the actual, immediate
  owner need (show one option correctly) without touching the carousel wire format
  at all. The template-free switch is a real, independently valuable simplification
  (no template registration/approval wait for catalogue browsing) but belongs to the
  cross-service GALLERY-unification slice the taxonomy doc already flags, not to this
  single-item feature. Bundling it here would risk the single-item fix on an
  unrelated, larger migration.

## 9. Full loop, traced end to end — single-item case

1. Customer asks about services in chat; the LLM adapter proposes
   `suggest_services_carousel` (unchanged tool name, per §7's collapsed design) —
   `app/adapters/llm/assistant_service.py` returns the `ToolCall`.
2. `_route_to_llm` (`conversation.py:1435-1450`) calls
   `T.validate_and_render(tool="suggest_services_carousel", ...)`.
3. Inside `tools.py`, `catalog_provider.list_cards` returns real candidates; exactly
   one has `image_url != ""` this time. The `== 1` branch (§7) returns
   `RenderedSingleCard(card=that_one)`.
4. `conversation.py`'s new `isinstance(result, T.RenderedSingleCard)` branch
   (§4) sets `conv.shown_carousel_ids = [card.id]`, saves conversation state, and
   returns `ReplyPlan(kind="card", card=result)`.
5. The API layer's `ReplyPlan.kind` switch (wherever `app/api/internal.py` or its
   webhook handler dispatches `ReplyPlan` to a `WhatsAppSender`) gains one arm:
   `"card"` → `sender.send_single_card(tenant=..., to=..., card=result.card.card,
   idempotency_key=...)` — the new adapter method from §5.
6. `CarouselSender.send_single_card` fetches the one photo, uploads it for a
   `media_id`, POSTs one interactive-style message with body `card.name`/price and
   one `quick_reply` button payload `f"carousel:{card.kind}:{card.id}"` — identical
   payload shape to one card in today's carousel, just delivered alone.
7. Customer taps the button. Meta's webhook → notification-service →
   whatsapp-assistant's inbound handler → `handle_button_reply(reply_id="carousel:
   service:svc_123", ...)` (`conversation.py:1635-1662`) — **exactly the existing
   carousel-tap code path, unmodified.**
8. `_handle_button_reply_locked` sees the `"carousel:"` prefix, calls
   `_handle_carousel_pick` (`conversation.py:1656-1658`), which checks `item_id in
   conv.shown_carousel_ids` — true, since step 4 populated it with exactly that id
   — then calls `_availability_for` → real slots → `_propose_slot`
   (`conversation.py:1504-1545`), which builds a `RenderedProposal` (never a model
   guess) and returns `ReplyPlan(kind="interactive", proposal=result)`.
9. Confirmation proceeds through `handle_button_reply`'s existing
   proposal-id-gated branch (`conversation.py:1652-1725`) exactly as any carousel or
   chat-typed booking already does — one booking engine, reached by a single-item
   tap the same way a carousel tap reaches it. No new booking code exists or is
   needed anywhere past step 6.

## 10. Ordered, testable implementation slices

1. Add `RenderedSingleCard` dataclass next to `RenderedCarousel` in `tools.py`
   (§2). No behavior change yet — dead code, unit-testable in isolation.
2. Change `suggest_services_carousel`'s branch from `if len(with_images) < 2` to the
   three-way split in §7 (`== 0` / `== 1` / `>= 2`). Unit test: exactly one
   photographed candidate now returns `RenderedSingleCard`, not the apology text.
3. Add `ReplyPlan.card` field and the `"card"` kind (§4); add the
   `isinstance(result, T.RenderedSingleCard)` branch in `conversation.py`, mirroring
   the `RenderedCarousel` branch line-for-line with a one-element list. Unit test:
   `conv.shown_carousel_ids` is populated correctly and `ReplyPlan.kind == "card"`.
4. Add `send_single_card`/its `Null...` counterpart to `carousel.py` (§5), reusing
   `_fetch_image`/`_upload_media_id` unchanged. Unit test against a fake
   notification-service response, same style as existing `CarouselSender` tests.
5. Wire the API layer's `ReplyPlan.kind` dispatch to call the new sender method on
   `"card"`. Integration test: a one-candidate catalog end-to-end produces a real
   `send_single_card` call, not a text apology.
6. Full loop test: a single-item response's button tap resolves to a real
   `RenderedProposal` through the unchanged `_handle_carousel_pick` path — proves
   §3's "zero changes needed" claim by running it, not just asserting it.
7. **Not in scope for this feature, tracked separately per §8**: the
   template-free interactive-carousel migration for `wa_catalog_carousel` — belongs
   with reminders' own GALLERY-unification work (taxonomy doc edge case #1), not
   bundled into this slice.

Explicitly NOT reusable here, and why: reminders' `send_media()` (§6, wrong
transport/recipient-resolution/template model for the bot); the `button_item_id`/
`button_kind` parameters on reminders' own `HttpSender.send()`/`send_media()` (those
are campaigns' INVITE-quick-reply mechanism, a different caller entirely — the bot's
new `send_single_card` carries its own button payload construction, not those
parameters). Directly reusable: `CarouselSender`'s existing `_fetch_image`/
`_upload_media_id` helpers (§5), and the entire `"carousel:{kind}:{item_id}"`
reply-id/binding mechanism (§3) with no changes at all.
