"""العائلة ج — one act, two calls, and one of them asked a smaller question.

Every defect here is a DEFAULT that decided policy while both calls stayed valid. Nothing raised,
nothing logged, and each pair produced two answers from the same function on the same data — which
is exactly why nobody read the argument list.
"""
from __future__ import annotations

import asyncio
import inspect

from app.core.dispatch import Dispatcher
from app.core.spread import plan


def run(c):
    return asyncio.run(c)


# ── ج-1 · the preview and the send resolved under different rulebooks ──────────────────────────
def test_the_resolver_refuses_to_guess_which_rules_apply():
    """`cls` decides WHICH RULES an audience is resolved under: marketing needs explicit consent
    and four messages a month, awareness needs neither. The send passed the campaign's real class;
    the preview took the default. So an awareness campaign was previewed under marketing rules and
    executed under awareness rules — the screen said 12 and the run reached 180.

    THE FIX IS THE ABSENCE OF A DEFAULT. A caller that does not say now cannot call at all, which
    is worth more than any check that could have caught the omission after the fact.
    """
    from app.container import _AudienceFacade

    sig = inspect.signature(_AudienceFacade.resolve_for)
    assert sig.parameters["cls"].default is inspect.Parameter.empty, (
        "a default here is a policy chosen by whoever forgets to pass one")


def test_the_preview_asks_with_the_goal_s_own_class():
    """And it takes it from `resolve_goal` — the one place that maps a goal to its class — rather
    than deriving it a second time beside the first."""
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "campaigns.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "preview")
    call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "resolve_for")
    passed = {k.arg: ast.unparse(k.value) for k in call.keywords}

    assert passed.get("cls") == "spec['cls']", passed


# ── ج-3 · zero meant «exhausted» and «unknown» at once ─────────────────────────────────────────
class _Sender:
    def __init__(self):
        self.sent = []

    async def send(self, **kw):
        self.sent.append(kw)
        return {"sent": True, "reason": ""}


class _Audience:
    count = 3

    class _C:
        def __init__(self, ref):
            self.subject_ref = ref

    candidates = [_C("sub_a"), _C("sub_b"), _C("sub_c")]
    excluded = 0


def _dispatcher(sender):
    async def resolver(campaign, *, already_reached, now):
        return _Audience()

    return Dispatcher(store=_Store(), sender=sender, audience_resolver=resolver, batch=200)


class _Store:
    def __init__(self):
        self.rows = {}

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def find(self, collection, query, **kw):
        return [], None


def test_a_spent_ceiling_sends_nothing_rather_than_a_whole_batch():
    """`share.py` answers `per_day=0, known=True` when today's allowance is gone. The sender read
    it with `or` — falsy for exactly that value — and fell through to the pass batch. The preview
    refused with «لا تتوفر مساحة اليوم» and the send pushed 200 messages past the ceiling, where
    the failures landed on whichever message went last: a customer's confirmation, not the campaign
    that caused it."""
    sender = _Sender()
    d = _dispatcher(sender)

    run(d.fire({"tenant": "t1", "id": "c1"}, now=1_000, daily_share=0))

    assert sender.sent == [], "zero is a real answer and it means «not today»"


def test_an_unknown_share_still_sends_under_the_pass_bound():
    """The other direction: an unreadable ceiling is our outage, and silencing a shop over it
    would be worse than the ceiling it could not read."""
    sender = _Sender()
    d = _dispatcher(sender)

    run(d.fire({"tenant": "t1", "id": "c2"}, now=1_000, daily_share=None))

    assert len(sender.sent) == 3


# ── ج-4 · the spread refusal was computed and never enforced ───────────────────────────────────
def test_a_campaign_that_cannot_finish_before_its_offer_expires_sends_nothing():
    """10,000 recipients, a share of 500 and an offer that ends in five days: ~2,500 arrive and
    7,500 sit queued for an offer that has expired — every one a message the shop pays for and a
    customer told about a discount he cannot have. `spread.plan` said so at preview and named both
    remedies; the launch called nothing.
    """
    sender = _Sender()
    d = _dispatcher(sender)
    day = 86_400
    now = 1_000_000

    out = run(d.fire({"tenant": "t1", "id": "c3", "expires_at": now + day},
                     now=now, daily_share=1))

    assert sender.sent == [], "a partial send is the outcome the refusal exists to prevent"
    assert any("لن تصل الحملة للجميع" in r for r in out.run.reasons), out.run.reasons


def test_a_campaign_that_fits_is_not_refused():
    """The guard must not eat the ordinary case: an audience that fits inside the days it has
    left runs, and runs on the first pass."""
    sender = _Sender()
    d = _dispatcher(sender)
    day = 86_400
    now = 1_000_000

    run(d.fire({"tenant": "t1", "id": "c4", "expires_at": now + 30 * day},
               now=now, daily_share=100))

    assert len(sender.sent) == 3


def test_a_campaign_with_no_expiry_is_never_refused_for_time():
    """«أعلن جديدك» has no deadline. Refusing it for one would be inventing a rule the owner never
    set — the same shape as the defect, in the other direction."""
    sender = _Sender()
    d = _dispatcher(sender)

    run(d.fire({"tenant": "t1", "id": "c5"}, now=1_000_000, daily_share=1))

    assert len(sender.sent) == 1, "bounded by the share, not refused by a deadline it does not have"


def test_the_plan_still_names_both_remedies():
    """The sentence is the product here: an owner who is only told «no» cannot act, and only he
    can choose between a smaller audience and a later date."""
    p = plan(audience=10_000, available_per_day=500, expires_at=1_000_000 + 5 * 86_400,
             now=1_000_000)
    assert "صغّر الجمهور" in p.refused and "مدّد التاريخ" in p.refused
