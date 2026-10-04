"""Operations' own step catalog for `common/story.py`'s autonomous composer — the app owning its
domain knowledge, the same split every other `apps/<name>/` module already holds. Built entirely
on Actions this session already hand-wrote and proved (`actions.py`, `mobile_requests_actions.py`)
— the composer adds no new HTTP logic, only the CHOICE of when each one is even a valid move.

SELF-CONTAINED ON PURPOSE: no `hire_member`/branch-scoping steps here, so this whole story runs
against ONE spawned services/operations with no identity-service peer needed — that combination is
already proven for real elsewhere (`test_stage10_branches.py`, `test_stage14_integration.py`).
`AssignMobileRequestAction`'s own `operator_id` never needs a real Operator row to succeed (see
that action's own docstring), so a synthetic id is a real, valid move here, not a shortcut.
"""
from __future__ import annotations

import random

from simulator.common.story import StoryStep, World

from .actions import AddAffiliateAction, CreateBranchAction, RecordUniqueVisitAction, RegisterUniqueReferralAction
from .mobile_requests_actions import (
    AcceptMobileRequestAction, AssignMobileRequestAction, CompleteMobileRequestAction,
    CreateMobileRequestAction, NoShowMobileRequestAction, RejectMobileRequestAction,
)


def _rand_phone(rng: random.Random) -> str:
    return f"05{rng.randint(10_000_000, 99_999_999)}"


def _pending_ids(world: World) -> list[str]:
    return [rid for rid, status in world["requests"].items() if status == "pending"]


def _accepted_ids(world: World) -> list[str]:
    return [rid for rid, status in world["requests"].items() if status == "accepted"]


def new_world() -> World:
    """A fresh, empty world for one story run — every step's own `eligible()` reads these same
    four keys, so a caller never needs to know their shape beyond passing this straight through."""
    return {"branch_ids": [], "affiliate_codes": [], "requests": {}, "assigned_operators": []}


def build_steps(base_url: str, tenant: str, *,
                max_branches: int = 4, max_affiliates: int = 3,
                max_requests: int = 8) -> list[StoryStep]:
    """One step per real business move this app's own actions already prove work — the composer
    picks freely among whichever are ELIGIBLE against the world state a PRIOR step actually
    produced, never a fixed order."""

    steps: list[StoryStep] = []

    steps.append(StoryStep(
        name="create_branch",
        eligible=lambda w: len(w["branch_ids"]) < max_branches,
        build=lambda w, rng: CreateBranchAction(
            base_url=base_url, tenant=tenant, branch_name=f"فرع {len(w['branch_ids']) + 1}"),
        after=lambda w, r: w["branch_ids"].append(r.data["id"]),
    ))

    steps.append(StoryStep(
        name="record_visit",
        eligible=lambda w: True,
        build=lambda w, rng: RecordUniqueVisitAction(base_url=base_url, tenant=tenant),
        after=lambda w, r: None,
        weight=2.0,  # the most common real move at any real shop, weighted to match.
    ))

    steps.append(StoryStep(
        name="add_affiliate",
        eligible=lambda w: len(w["affiliate_codes"]) < max_affiliates,
        build=lambda w, rng: AddAffiliateAction(
            base_url=base_url, tenant=tenant, phone=_rand_phone(rng),
            code=f"CODE{len(w['affiliate_codes']) + rng.randint(1000, 9999)}", discount_percent=10),
        after=lambda w, r: w["affiliate_codes"].append(r.data["code"]),
    ))

    steps.append(StoryStep(
        name="register_referral",
        eligible=lambda w: bool(w["affiliate_codes"]),
        build=lambda w, rng: RegisterUniqueReferralAction(
            base_url=base_url, tenant=tenant, code=rng.choice(w["affiliate_codes"])),
        after=lambda w, r: None,
    ))

    steps.append(StoryStep(
        name="create_mobile_request",
        eligible=lambda w: len(w["requests"]) < max_requests,
        build=lambda w, rng: CreateMobileRequestAction(
            base_url=base_url, tenant=tenant, phone=_rand_phone(rng)),
        after=lambda w, r: w["requests"].__setitem__(r.data["id"], r.data["status"]),
    ))

    steps.append(StoryStep(
        name="assign_mobile_request",
        eligible=lambda w: bool(_pending_ids(w)),
        build=lambda w, rng: AssignMobileRequestAction(
            base_url=base_url, tenant=tenant, request_id=rng.choice(_pending_ids(w)),
            operator_id=f"op-story-{rng.randint(1, 9999)}"),
        after=lambda w, r: w["assigned_operators"].append(r.data.get("assigned_to", "")),
    ))

    steps.append(StoryStep(
        name="accept_mobile_request",
        eligible=lambda w: bool(_pending_ids(w)),
        build=lambda w, rng: AcceptMobileRequestAction(
            base_url=base_url, tenant=tenant, request_id=rng.choice(_pending_ids(w))),
        after=lambda w, r: w["requests"].__setitem__(r.data["id"], r.data["status"]),
    ))

    steps.append(StoryStep(
        name="reject_mobile_request",
        eligible=lambda w: bool(_pending_ids(w)),
        build=lambda w, rng: RejectMobileRequestAction(
            base_url=base_url, tenant=tenant, request_id=rng.choice(_pending_ids(w)),
            reason="بعيد عن نطاق الخدمة"),
        after=lambda w, r: w["requests"].__setitem__(r.data["id"], r.data["status"]),
    ))

    steps.append(StoryStep(
        name="complete_mobile_request",
        eligible=lambda w: bool(_accepted_ids(w)),
        build=lambda w, rng: CompleteMobileRequestAction(
            base_url=base_url, tenant=tenant, request_id=rng.choice(_accepted_ids(w))),
        after=lambda w, r: w["requests"].__setitem__(r.data["id"], r.data["status"]),
    ))

    steps.append(StoryStep(
        name="no_show_mobile_request",
        eligible=lambda w: bool(_accepted_ids(w)),
        build=lambda w, rng: NoShowMobileRequestAction(
            base_url=base_url, tenant=tenant, request_id=rng.choice(_accepted_ids(w))),
        after=lambda w, r: w["requests"].__setitem__(r.data["id"], r.data["status"]),
    ))

    return steps
