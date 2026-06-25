from unittest.mock import AsyncMock, patch

import pytest

from database_utils.services.email_service import SMTPEmailService


@pytest.fixture
def smtp_service():
    return SMTPEmailService(
        host="smtp.hostinger.com",
        port=465,
        username="noreply@example.com",
        password="secret",
        from_address="noreply@example.com",
        use_tls=True,
    )


@pytest.mark.asyncio
async def test_send_confirmation_email_calls_smtp_send(smtp_service):
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        result = await smtp_service.send_confirmation_email(
            to_email="user@example.com",
            confirmation_link="https://app.example.com/confirm-email?token=abc",
            user_name="Jane",
        )
    assert result is True
    mock_send.assert_called_once()
    _, kwargs = mock_send.call_args
    assert kwargs["hostname"] == "smtp.hostinger.com"
    assert kwargs["port"] == 465


@pytest.mark.asyncio
async def test_send_confirmation_email_returns_false_on_error(smtp_service):
    with patch("aiosmtplib.send", new_callable=AsyncMock, side_effect=OSError("connection refused")):
        result = await smtp_service.send_confirmation_email(
            to_email="user@example.com",
            confirmation_link="https://app.example.com/confirm-email?token=abc",
            user_name="Jane",
        )
    assert result is False
