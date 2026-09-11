"""The settings an operator may change at runtime, for this service.

DECLARING A KEY HERE IS A PROMISE THAT SOMETHING READS IT through RuntimeConfig at the point of
use. That promise is the entire point: offering every settable field to the panel instead fails in
the most convincing way available — the panel accepts the change, the audit log records it with an
actor and a timestamp, and behaviour does not move, because nothing consults the override. The
operator ends up holding a receipt for a change that never happened.

The generated service starts with none, deliberately. Add a key here in the same change that wires
the read, never before: unavailable is honest, inert is not.

FIXED 2026-09-12, A REAL GAP A QA AUDIT FOUND: this stayed the template's empty frozenset() while
admin_actions.py's own help text already told an operator these two were "the only two settings
today" — GET /api/v1/operator/config rendered an empty panel and every PUT was refused with
"cannot be changed at runtime", contradicting the very screen it was on. The read side (SignalStore/
TemplateErasure's retention_days, the ingest/report routes' reap_limit — see app/api/internal.py
and app/api/v1/signals.py) now resolves through RuntimeConfig.get() in the same change that adds
these two keys here, so declaring them is no longer a promise nothing keeps.
"""
from __future__ import annotations

RUNTIME_POLICY: frozenset[str] = frozenset({"SIGNAL_RETENTION_DAYS", "SIGNAL_REAP_LIMIT"})
