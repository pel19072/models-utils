import pytest
from pydantic import ValidationError

from database_utils.schemas.email_verification import (
    ConfirmEmailValidate, ConfirmEmailRequest, ResendConfirmationRequest
)
from database_utils.schemas.password_reset import (
    PasswordResetRequestSchema, PasswordResetValidate, PasswordResetConfirmSchema
)


def test_confirm_email_request_requires_token():
    with pytest.raises(ValidationError):
        ConfirmEmailRequest()
    req = ConfirmEmailRequest(token="abc")
    assert req.token == "abc"


def test_resend_confirmation_request_validates_email():
    with pytest.raises(ValidationError):
        ResendConfirmationRequest(email="not-an-email")
    req = ResendConfirmationRequest(email="user@example.com")
    assert req.email == "user@example.com"


def test_confirm_email_validate_defaults():
    out = ConfirmEmailValidate(token="abc", valid=False, message="Invalid")
    assert out.email is None


def test_password_reset_request_validates_email():
    with pytest.raises(ValidationError):
        PasswordResetRequestSchema(email="nope")
    req = PasswordResetRequestSchema(email="user@example.com")
    assert req.email == "user@example.com"


def test_password_reset_confirm_requires_new_password():
    with pytest.raises(ValidationError):
        PasswordResetConfirmSchema(token="abc", new_password="short")
    req = PasswordResetConfirmSchema(token="abc", new_password="longenough1")
    assert req.new_password == "longenough1"


def test_password_reset_validate_defaults():
    out = PasswordResetValidate(token="abc", valid=False, message="Invalid")
    assert out.email is None
