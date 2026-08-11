"""The till's door — the properties that stop one shop's cashier writing into another's data.

These are the assertions the old internal route could not have passed, and the reason it could not
be handed to an outside party at all.
"""
from __future__ import annotations

import inspect

from app.api.v1 import till


def test_the_request_model_has_no_tenant_field():
    """THE WHOLE SECURITY PROPERTY, asserted at the shape rather than at the handler.

    A `tenant` field that the handler currently ignores is one refactor away from being read
    "just for validation", and then from being trusted. The field does not exist, so there is
    nothing to start trusting — and this test fails the day somebody adds it back.
    """
    assert "tenant" not in till.TillVisitIn.model_fields
    assert "tenant" not in till.TillBatchIn.model_fields


def test_the_tenant_is_taken_from_the_principal():
    """Read off the token, in one place, and nowhere else."""
    source = inspect.getsource(till.record_from_till)
    assert "tenant = principal.tenant" in source
    # And nothing reads it back off an item.
    assert "v.tenant" not in source
    assert "item.tenant" not in source


def test_a_token_with_no_tenant_is_refused_rather_than_widened():
    """A missing tenant claim must never become "all tenants" — the classic widening (T8)."""
    source = inspect.getsource(till.record_from_till)
    assert "if not principal.tenant:" in source


def test_it_requires_exactly_the_recording_capability():
    """One capability, and the same one the operator at the counter holds.

    Named here so a widening — `operations.manage`, say, to let a till create a branch — is a
    deliberate edit to a test rather than a quiet line in a router.
    """
    source = inspect.getsource(till)
    assert 'require_capability("operations.record")' in source
    assert "require_internal_token" not in source
