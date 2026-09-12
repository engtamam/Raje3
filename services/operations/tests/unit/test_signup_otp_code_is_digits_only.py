"""operations-r2-007 (QA audit round 2, 2026-09-12): the signup OTP `code` field used to accept
any short string — only its length was bounded. Same convention `connect.py`'s `RegisterIn.pin`
already uses for a code that reaches a peer over the network: shape-checked before it travels."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.signup import ClaimIn, OpenShopIn, ProveIn, SignInIn


@pytest.mark.parametrize("model, extra", [
    (ProveIn, {"phone": "0501234567"}),
    (ClaimIn, {"phone": "0501234567", "password": "pw"}),
])
def test_a_non_digit_otp_code_is_refused(model, extra):
    with pytest.raises(ValidationError):
        model(code="ab12", **extra)


@pytest.mark.parametrize("model, extra", [
    (ProveIn, {"phone": "0501234567"}),
    (ClaimIn, {"phone": "0501234567", "password": "pw"}),
])
def test_a_real_digit_otp_code_still_works(model, extra):
    assert model(code="123456", **extra).code == "123456"


@pytest.mark.parametrize("model, extra", [
    (OpenShopIn, {"phone": "0501234567", "password": "pw", "shop_name": "محلي"}),
    (SignInIn, {"phone": "0501234567", "password": "pw"}),
])
def test_the_optional_code_rejects_non_digits_but_allows_empty(model, extra):
    assert model(code="", **extra).code == ""
    with pytest.raises(ValidationError):
        model(code="ab12", **extra)
