"""Validating one of the eight reward shapes (spec §4) — pure, no store, no I/O.

EVERY VALIDATOR RETURNS THE NORMALIZED PARAMS IT WOULD ACTUALLY STORE, never just True/False — the
caller (`campaigns.py::create`) writes exactly what comes back here, so a validated campaign and a
stored campaign can never quietly disagree about, say, whether "percent" arrived as a string.

NO CATALOGUE LOOKUP HERE, ON PURPOSE. `milestone_free_item` names a service by id+name the caller
already resolved against their own shop's catalogue (owned by `services/operations`, a different
service this one never calls synchronously) — this module only checks the two strings are real,
non-empty text, the same "no free text, a real item from a real list" rule the mutual-benefit
gift design already established, enforced one layer up from here rather than by a cross-service
call this phase does not need yet.
"""
from __future__ import annotations

from typing import Any

from app.core.models import (
    NEW_CUSTOMER_DISCOUNT_PERCENT, NEW_CUSTOMER_WELCOME_POINTS,
    REWARD_CASHBACK_POINTS, REWARD_FIXED_POINTS, REWARD_INVOICE_PERCENTAGE,
    REWARD_MILESTONE_FREE_ITEM, REWARD_MYSTERY_BOX, REWARD_POINTS_MATCH,
    REWARD_STATUS_MULTIPLIER, REWARD_TIME_BOOST,
)

_MAX_PERCENT = 99
_MAX_MULTIPLIER = 10.0


class RewardError(Exception):
    """A refusal a caller should show verbatim — never a stack trace."""


def _positive_int(value: Any, *, field: str, minimum: int = 1) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise RewardError(f"{field}: قيمة غير صالحة")
    if n < minimum:
        raise RewardError(f"{field}: يجب أن يكون {minimum} على الأقل")
    return n


def _percent(value: Any, *, field: str) -> int:
    n = _positive_int(value, field=field)
    if n > _MAX_PERCENT:
        raise RewardError(f"{field}: لا يمكن أن يتجاوز {_MAX_PERCENT}%")
    return n


def _multiplier(value: Any, *, field: str) -> float:
    try:
        m = float(value)
    except (TypeError, ValueError):
        raise RewardError(f"{field}: قيمة غير صالحة")
    if not (1.0 < m <= _MAX_MULTIPLIER):
        raise RewardError(f"{field}: يجب أن يكون بين 1 و{_MAX_MULTIPLIER}")
    return m


def _non_empty_text(value: Any, *, field: str) -> str:
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        raise RewardError(f"{field}: مطلوب")
    return text


def _validate_fixed_points(params: dict[str, Any]) -> dict[str, Any]:
    return {"points": _positive_int(params.get("points"), field="عدد النقاط")}


def _validate_invoice_percentage(params: dict[str, Any]) -> dict[str, Any]:
    return {"percent": _percent(params.get("percent"), field="نسبة الفاتورة")}


def _validate_points_match(params: dict[str, Any]) -> dict[str, Any]:
    return {"percent": _percent(params.get("percent"), field="نسبة مطابقة النقاط")}


def _validate_milestone_free_item(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "referrals_required": _positive_int(params.get("referrals_required"),
                                            field="عدد الإحالات المطلوبة"),
        "service_id": _non_empty_text(params.get("service_id"), field="الخدمة"),
        "service_name": _non_empty_text(params.get("service_name"), field="اسم الخدمة"),
    }


def _validate_cashback_points(params: dict[str, Any]) -> dict[str, Any]:
    # SAME SHAPE AS fixed_points, DELIBERATELY — the only difference is the TAG this reward is
    # recorded under at redemption time (Phase 3), which is a fact about WHERE the points are
    # spent from, never about how many are granted here.
    return {"points": _positive_int(params.get("points"), field="عدد نقاط الكاش باك")}


def _validate_status_multiplier(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "referrals_required": _positive_int(params.get("referrals_required"),
                                            field="عدد الإحالات للترقية"),
        "multiplier": _multiplier(params.get("multiplier"), field="مضاعف النقاط"),
    }


def _validate_time_boost(params: dict[str, Any]) -> dict[str, Any]:
    windows = params.get("windows") or []
    if not windows:
        raise RewardError("أوقات التعزيز: يجب تحديد نافذة زمنية واحدة على الأقل")
    normalized = []
    for w in windows:
        try:
            weekday, start, end = int(w["weekday"]), int(w["start_minute"]), int(w["end_minute"])
        except (KeyError, TypeError, ValueError):
            raise RewardError("أوقات التعزيز: نافذة زمنية غير صالحة")
        if not (0 <= weekday <= 6):
            raise RewardError("أوقات التعزيز: يوم غير صالح — يجب أن يكون بين 0 و6")
        if not (0 <= start < end <= 24 * 60):
            raise RewardError(f"أوقات التعزيز: نافذة غير صالحة: {start}-{end}")
        normalized.append({"weekday": weekday, "start_minute": start, "end_minute": end})
    return {"multiplier": _multiplier(params.get("multiplier"), field="مضاعف وقت الركود"),
            "windows": normalized}


def _validate_mystery_box(params: dict[str, Any]) -> dict[str, Any]:
    outcomes = params.get("outcomes") or []
    if len(outcomes) < 2:
        raise RewardError("صندوق الحظ: يحتاج احتمالين على الأقل")
    normalized = []
    for o in outcomes:
        points = _positive_int(o.get("points"), field="نقاط احتمال بصندوق الحظ")
        weight = _positive_int(o.get("weight"), field="وزن احتمال بصندوق الحظ")
        normalized.append({"points": points, "weight": weight})
    return {"outcomes": normalized}


_REWARD_VALIDATORS = {
    REWARD_FIXED_POINTS: _validate_fixed_points,
    REWARD_INVOICE_PERCENTAGE: _validate_invoice_percentage,
    REWARD_POINTS_MATCH: _validate_points_match,
    REWARD_MILESTONE_FREE_ITEM: _validate_milestone_free_item,
    REWARD_CASHBACK_POINTS: _validate_cashback_points,
    REWARD_STATUS_MULTIPLIER: _validate_status_multiplier,
    REWARD_TIME_BOOST: _validate_time_boost,
    REWARD_MYSTERY_BOX: _validate_mystery_box,
}


def validate_reward(reward_type: str, params: dict[str, Any]) -> dict[str, Any]:
    validator = _REWARD_VALIDATORS.get(reward_type)
    if validator is None:
        raise RewardError(f"نوع مكافأة غير معروف: {reward_type}")
    return validator(params or {})


def _validate_new_customer_discount(params: dict[str, Any]) -> dict[str, Any]:
    return {"percent": _percent(params.get("percent"), field="نسبة خصم العميل الجديد")}


def _validate_new_customer_welcome_points(params: dict[str, Any]) -> dict[str, Any]:
    return {"points": _positive_int(params.get("points"), field="نقاط ترحيب العميل الجديد")}


_NEW_CUSTOMER_VALIDATORS = {
    NEW_CUSTOMER_DISCOUNT_PERCENT: _validate_new_customer_discount,
    NEW_CUSTOMER_WELCOME_POINTS: _validate_new_customer_welcome_points,
}


def validate_new_customer_reward(reward_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """The mandatory 'win-win' half (spec §4c) — a campaign with no honest answer here must never
    be creatable at all; see `campaigns.py::create`, which calls this unconditionally, never behind
    an `if`."""
    validator = _NEW_CUSTOMER_VALIDATORS.get(reward_type)
    if validator is None:
        raise RewardError(f"نوع مكافأة غير معروف للعميل الجديد: {reward_type}")
    return validator(params or {})
