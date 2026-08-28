"""core/sending_identity.split — the inverse of operations-service's own mint function. See this
module's own docstring for why whatsapp-assistant carries a copy rather than importing it."""
from __future__ import annotations

from app.core.sending_identity import split


def test_a_central_shops_plain_tenant_splits_to_itself_with_no_branch():
    assert split("tenant-abc") == ("tenant-abc", "")


def test_a_per_branch_composite_splits_into_tenant_and_branch():
    assert split("tenant-abc:brn-jed") == ("tenant-abc", "brn-jed")


def test_empty_and_none_split_to_two_empty_strings():
    assert split("") == ("", "")
    assert split(None) == ("", "")  # type: ignore[arg-type]


def test_only_the_first_colon_separates_tenant_from_branch():
    """A branch id containing its own colon (unlikely, but never assumed) must not truncate."""
    assert split("tenant-abc:brn:extra") == ("tenant-abc", "brn:extra")


def test_a_bare_colon_with_nothing_after_it_is_an_empty_branch_not_a_missing_split():
    assert split("tenant-abc:") == ("tenant-abc", "")
