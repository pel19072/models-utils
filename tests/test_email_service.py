import pytest

from database_utils.services.email_service import MockEmailService


@pytest.mark.asyncio
async def test_send_confirmation_email_returns_true():
    service = MockEmailService()
    result = await service.send_confirmation_email(
        to_email="user@example.com",
        confirmation_link="https://app.example.com/confirm-email?token=abc",
        user_name="Jane",
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_password_reset_email_returns_true():
    service = MockEmailService()
    result = await service.send_password_reset_email(
        to_email="user@example.com",
        reset_link="https://app.example.com/reset-password?token=abc",
        user_name="Jane",
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_payment_failed_email_returns_true():
    service = MockEmailService()
    result = await service.send_payment_failed_email(
        to_email="admin@example.com",
        company_name="Acme Inc",
        invoice_data={"invoice_number": "INV-1", "total": 9900},
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_join_request_decision_email_approved():
    service = MockEmailService()
    result = await service.send_join_request_decision_email(
        to_email="user@example.com",
        user_name="Jane",
        company_name="Acme Inc",
        approved=True,
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_join_request_decision_email_rejected():
    service = MockEmailService()
    result = await service.send_join_request_decision_email(
        to_email="user@example.com",
        user_name="Jane",
        company_name="Acme Inc",
        approved=False,
    )
    assert result is True
