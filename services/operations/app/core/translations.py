"""Hash-based change detection for shop-written Arabic text — a service's `name`/`description`, a
`ProcedureStep.text` — that a shop enters once and never in any language but Arabic.

WHY A HASH, NOT A TIMESTAMP OR A DIRTY FLAG. `save()` runs on every edit whether or not the
translatable field actually changed (a service's `sort` or `active` flips constantly; its `name`
rarely does). Hashing the field's OWN VALUE and comparing against the last hash a translation was
produced for means an edit to an unrelated field costs nothing — same hash in, no-op — and an edit
that changes the text back to a PREVIOUS value is recognised as already-translated rather than
re-queued, which a boolean dirty flag or a bare `updated_at` bump could never tell apart.

THIS MODULE DOES NOT TRANSLATE ANYTHING. It only decides "does this field's current text match what
was last translated" and, when it does not, resets the stored entry to `status="pending"` with
empty `translations` — the queue/worker that actually fills them in is later work (see
[[task-catalog-translation-phases]] memory). Until that worker exists, every entry simply sits at
`pending` forever, which is a correct, honest state — never a blank field or a crash.
"""
from __future__ import annotations

import hashlib
import time

from app.core.models import TranslationEntry

# EVERY OPERATOR LOCALE EXCEPT ARABIC ITSELF — see `operator-i18n.tsx`'s own `OperatorLocale`.
# Arabic is always the source, never a translation target.
TARGET_LOCALES: tuple[str, ...] = ("en", "ur", "ha", "fil", "bn")


def content_hash(text: str) -> str:
    """A stable fingerprint of exactly this text — same input, same hash, forever. `sha256` rather
    than Python's own `hash()`: the latter is salted per-process (`PYTHONHASHSEED`), so two
    processes (or two runs of the same one) would disagree about whether a field had changed."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entry_id(entity_type: str, entity_id: str, field: str) -> str:
    """Deterministic key — `TranslationStore.get`/`_put` never need a lookup to find the ONE row
    that already exists for a given (entity_type, entity_id, field), same "direct key, never a
    find" shape `OperatorStepStat.id`'s own docstring already argues for."""
    return f"{entity_type}:{entity_id}:{field}"


def resolve(entry: TranslationEntry | None, locale: str, fallback: str) -> str:
    """The text to SHOW for one field in one locale — never a blank, never an error.

    Arabic itself, or a locale with no entry at all (an untranslated field, or a worker that has
    not run yet), or an entry still `status="pending"`, all resolve to `fallback` — the shop's own
    Arabic text, which is always correct to show even when it is not the caller's own language.
    Only a locale actually present in `entry.translations` overrides it.
    """
    if locale == "ar" or entry is None:
        return fallback
    return entry.translations.get(locale) or fallback


def detect_change(existing: TranslationEntry | None, *, tenant: str, entity_type: str,
                  entity_id: str, field: str, source_text: str) -> TranslationEntry | None:
    """Compare `source_text`'s hash against `existing`'s own — the one decision this whole module
    exists to make. Returns the entry to save, or `None` when nothing changed (the common case on
    an ordinary edit that never touches this field).

    EMPTY TEXT IS NOT AN ENTRY. A service with no `description` yet has nothing to translate; an
    entry would sit at `pending` forever for a field that will never have Arabic content to answer
    from, and every locale-switch read would need to special-case it. Absence is the fallback: the
    console already shows `source_text` (empty) exactly like every other empty field.
    """
    if not source_text:
        return None
    new_hash = content_hash(source_text)
    if existing is not None and existing.source_hash == new_hash:
        return None
    return TranslationEntry(
        id=entry_id(entity_type, entity_id, field), tenant=tenant, entity_type=entity_type,
        entity_id=entity_id, field=field, source_text=source_text, source_hash=new_hash,
        translations={}, status="pending", updated_at=int(time.time()))
