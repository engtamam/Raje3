"""The one, UNIFIED category taxonomy for anything that reaches the TikTok assistant — a DM
message or a public comment alike, never two separate lists (the owner's own call, 2026-09-16:
the same underlying topic — "order still hasn't shipped" — can arrive through either channel, and
counting it under two different names would silently split one real, recurring issue into two
half-sized ones nobody notices is the same thing). WHERE a message arrived (DM vs. comment) is
recorded as a separate field on the row, never folded into the category name itself.

SEEDED FROM REAL PRECEDENT, NOT INVENTED: the e-commerce half from published help-desk taxonomy
best practice (order status/tracking, shipping, returns/refunds, product defect, pre-sale
question, payment, promotions — the same buckets any support-ticket tool ships with), the social
half from the standard comment-intent split (praise, complaint, question, purchase intent, spam) —
researched 2026-09-16, not guessed.

ADAPTIVE, NOT FIXED FOREVER — same shape Enterpret and similar tools call an "adaptive taxonomy".
The model is instructed (see marketplaces/tiktok_assistant.py::build_system_prompt) to fit a
message into one of THESE first; only when genuinely none fits does it propose a new slug, which
lands in `pending` (TikTokShopService.record_message_category) for an owner/operator to approve or
merge into an existing one — never silently promoted to a real category on its own.
"""
from __future__ import annotations

#: (slug, Arabic label) — the slug is what the model is asked to emit and what a row's own
#: `category` field stores; the label is what an owner reads on a report.
KNOWN_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("order_status", "حالة الطلب وتتبعه"),
    ("shipping_delay", "تأخير أو مشكلة بالشحن"),
    ("return_refund", "إرجاع أو استرجاع"),
    ("product_defect", "عيب بالمنتج أو استلام شي غلط"),
    ("presale_question", "استفسار قبل الشراء"),
    ("payment", "الدفع والفوترة"),
    ("promotion", "العروض والخصومات"),
    ("account", "الحساب"),
    ("praise", "إشادة أو رضا"),
    ("complaint_other", "اعتراض أو شكوى — بلا تصنيف أدق"),
    ("purchase_intent", "نية شراء واضحة"),
    ("spam", "سبام أو محتوى غير مرتبط"),
)

KNOWN_SLUGS: frozenset[str] = frozenset(slug for slug, _ in KNOWN_CATEGORIES)


def label_for(slug: str) -> str:
    """The Arabic label for a known slug, or the slug itself for a still-`pending` one an owner
    has not named yet — never a blank, which would read as a row with no category at all."""
    for known_slug, label in KNOWN_CATEGORIES:
        if known_slug == slug:
            return label
    return slug


def catalogue_block() -> str:
    """The fixed list, rendered once for the system prompt — see build_system_prompt's own note
    on why this is INSIDE the stable, cacheable prefix rather than assembled per turn from a
    store read (it never changes at runtime; only an owner's own `pending` review promotes a new
    slug into a future code change here, not a live per-tenant list)."""
    return "\n".join(f"- {slug}: {label}" for slug, label in KNOWN_CATEGORIES)
