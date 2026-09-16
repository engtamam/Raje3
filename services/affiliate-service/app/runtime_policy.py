"""The settings an operator may change at runtime, for this service.

DECLARING A KEY HERE IS A PROMISE THAT SOMETHING READS IT through RuntimeConfig at the point of
use. That promise is the entire point: offering every settable field to the panel instead fails in
the most convincing way available — the panel accepts the change, the audit log records it with an
actor and a timestamp, and behaviour does not move, because nothing consults the override. The
operator ends up holding a receipt for a change that never happened.

The generated service starts with none, deliberately. Add a key here in the same change that wires
the read, never before: unavailable is honest, inert is not.
"""
from __future__ import annotations

RUNTIME_POLICY: frozenset[str] = frozenset({
    # The withdrawal threshold — OUR decision (platform-wide, never per-shop: there is no
    # establishment to scope it to). "400 ريال، وممكن يتغير" — read here on
    # every /me/home, /me/balance and withdrawal request (core/payouts.py's own
    # effective_min_withdrawal_halalas), so a panel change takes effect with no redeploy.
    "AFFILIATE_WITHDRAWAL_MIN_HALALAS",
    # Whether a manager's GET /me/team and GET /me/team/wafa-requests carry riyal figures at all —
    # read at the point of use in api/v1/affiliate_self.py. Off by default (config.py), and an
    # operator may turn it back on with no redeploy if the decision is ever reversed.
    "AFFILIATE_TEAM_FINANCIALS_VISIBLE",
})
