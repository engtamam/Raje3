"""app/config.py's two booking-management feature flags — BOOKING_MANAGEMENT_ENABLED (the master
kill-switch) and BOOKING_HISTORY_VISIBLE. Both must be flippable with a plain config value, no code
change — this proves `llm_tool_allowlist` (what a running process actually offers the LLM) reacts
to a value alone, not something that needs a re-deploy of new code to take effect."""
from app.config import Settings

_MANAGEMENT_TOOLS = {"list_my_bookings", "propose_cancel_booking", "propose_reschedule_booking"}


def test_booking_management_tools_are_declared_by_default():
    s = Settings(BOOKING_PROVIDER_DRIVER="real")
    assert _MANAGEMENT_TOOLS <= s.llm_tool_allowlist


def test_flipping_booking_management_enabled_off_drops_only_those_three_tools():
    s = Settings(BOOKING_PROVIDER_DRIVER="real", BOOKING_MANAGEMENT_ENABLED=False)
    assert s.llm_tool_allowlist.isdisjoint(_MANAGEMENT_TOOLS)
    # Everything else (booking creation, points, etc.) is UNAFFECTED — a targeted kill-switch,
    # not an accidental blast radius.
    assert "propose_booking" in s.llm_tool_allowlist
    assert "check_availability" in s.llm_tool_allowlist


def test_the_config_placeholder_driver_never_offers_booking_management_even_if_enabled():
    """ConfigDrivenAvailabilityProvider (BOOKING_PROVIDER_DRIVER="config", the zero-infra default)
    has no concept of a customer's real existing bookings — see booking_assignment.py's own
    module docstring. These tools must never be offered under it, regardless of
    BOOKING_MANAGEMENT_ENABLED, so a deployment that has not yet turned on the real driver cannot
    accidentally expose a broken/undefined booking-management surface."""
    s = Settings(BOOKING_PROVIDER_DRIVER="config", BOOKING_MANAGEMENT_ENABLED=True)
    assert s.llm_tool_allowlist.isdisjoint(_MANAGEMENT_TOOLS)


def test_booking_history_visible_defaults_true_and_is_independently_flippable():
    assert Settings().BOOKING_HISTORY_VISIBLE is True
    assert Settings(BOOKING_HISTORY_VISIBLE=False).BOOKING_HISTORY_VISIBLE is False
    # Flipping history visibility must never touch the management kill-switch or the base
    # allowlist string — the two flags are independent, per the plan's own design.
    s = Settings(BOOKING_PROVIDER_DRIVER="real", BOOKING_HISTORY_VISIBLE=False)
    assert s.BOOKING_MANAGEMENT_ENABLED is True
    assert _MANAGEMENT_TOOLS <= s.llm_tool_allowlist
