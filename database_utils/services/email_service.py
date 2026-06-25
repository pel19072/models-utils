from abc import ABC, abstractmethod
from typing import Dict, Any
from loguru import logger


class EmailService(ABC):
    """Abstract base class for email services"""

    @abstractmethod
    async def send_invitation_email(
        self, to_email: str, invitation_link: str, company_name: str, invited_by: str
    ) -> bool:
        """Send invitation email to new user"""
        pass

    @abstractmethod
    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """Send welcome email after user accepts invitation"""
        pass

    @abstractmethod
    async def send_payment_receipt(
        self, to_email: str, invoice_data: Dict[str, Any]
    ) -> bool:
        """Send payment receipt"""
        pass

    @abstractmethod
    async def send_confirmation_email(
        self, to_email: str, confirmation_link: str, user_name: str
    ) -> bool:
        """Send signup confirmation email; login is blocked until this link is clicked."""
        pass

    @abstractmethod
    async def send_password_reset_email(
        self, to_email: str, reset_link: str, user_name: str
    ) -> bool:
        """Send password reset email with a short-lived reset link."""
        pass

    @abstractmethod
    async def send_payment_failed_email(
        self, to_email: str, company_name: str, invoice_data: Dict[str, Any]
    ) -> bool:
        """Send notice that an automatic subscription charge could not be processed."""
        pass

    @abstractmethod
    async def send_join_request_decision_email(
        self, to_email: str, user_name: str, company_name: str, approved: bool
    ) -> bool:
        """Notify a join-request requester that an admin approved or rejected them."""
        pass


class MockEmailService(EmailService):
    """Mock email service for development/testing - logs to console"""

    async def send_invitation_email(
        self, to_email: str, invitation_link: str, company_name: str, invited_by: str
    ) -> bool:
        logger.info(
            f"[MOCK EMAIL] Invitation sent to {to_email}\n"
            f"Company: {company_name}\n"
            f"Invited by: {invited_by}\n"
            f"Link: {invitation_link}"
        )
        return True

    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        logger.info(f"[MOCK EMAIL] Welcome email sent to {to_email} ({user_name})")
        return True

    async def send_payment_receipt(
        self, to_email: str, invoice_data: Dict[str, Any]
    ) -> bool:
        logger.info(
            f"[MOCK EMAIL] Payment receipt sent to {to_email}\n"
            f"Invoice: {invoice_data.get('invoice_number')}\n"
            f"Amount: ${invoice_data.get('total', 0) / 100:.2f}"
        )
        return True

    async def send_confirmation_email(
        self, to_email: str, confirmation_link: str, user_name: str
    ) -> bool:
        logger.info(
            f"[MOCK EMAIL] Confirmation email sent to {to_email} ({user_name})\n"
            f"Link: {confirmation_link}"
        )
        return True

    async def send_password_reset_email(
        self, to_email: str, reset_link: str, user_name: str
    ) -> bool:
        logger.info(
            f"[MOCK EMAIL] Password reset email sent to {to_email} ({user_name})\n"
            f"Link: {reset_link}"
        )
        return True

    async def send_payment_failed_email(
        self, to_email: str, company_name: str, invoice_data: Dict[str, Any]
    ) -> bool:
        logger.info(
            f"[MOCK EMAIL] Payment failed notice sent to {to_email}\n"
            f"Company: {company_name}\n"
            f"Invoice: {invoice_data.get('invoice_number')}"
        )
        return True

    async def send_join_request_decision_email(
        self, to_email: str, user_name: str, company_name: str, approved: bool
    ) -> bool:
        decision = "approved" if approved else "rejected"
        logger.info(
            f"[MOCK EMAIL] Join request {decision} notice sent to {to_email} ({user_name})\n"
            f"Company: {company_name}"
        )
        return True


# Future Resend implementation (commented for reference):
# To enable Resend, uncomment and install resend: pip install resend
#
# from resend import Resend
#
# class ResendEmailService(EmailService):
#     def __init__(self, api_key: str):
#         self.client = Resend(api_key=api_key)
#
#     async def send_invitation_email(
#         self, to_email: str, invitation_link: str, company_name: str, invited_by: str
#     ) -> bool:
#         try:
#             self.client.emails.send({
#                 "from": "noreply@yourdomain.com",
#                 "to": to_email,
#                 "subject": f"You've been invited to join {company_name}",
#                 "html": f"<p>{invited_by} invited you to join {company_name}.</p><a href='{invitation_link}'>Accept Invitation</a>"
#             })
#             logger.info(f"Invitation email sent successfully to {to_email}")
#             return True
#         except Exception as e:
#             logger.error(f"Failed to send invitation email to {to_email}: {e}")
#             return False
#
#     async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
#         try:
#             self.client.emails.send({
#                 "from": "noreply@yourdomain.com",
#                 "to": to_email,
#                 "subject": "Welcome!",
#                 "html": f"<p>Welcome {user_name}! Your account is now active.</p>"
#             })
#             logger.info(f"Welcome email sent successfully to {to_email}")
#             return True
#         except Exception as e:
#             logger.error(f"Failed to send welcome email to {to_email}: {e}")
#             return False
#
#     async def send_payment_receipt(
#         self, to_email: str, invoice_data: Dict[str, Any]
#     ) -> bool:
#         try:
#             invoice_number = invoice_data.get('invoice_number')
#             total = invoice_data.get('total', 0) / 100
#             self.client.emails.send({
#                 "from": "billing@yourdomain.com",
#                 "to": to_email,
#                 "subject": f"Payment Receipt - {invoice_number}",
#                 "html": f"<p>Thank you for your payment of ${total:.2f}.</p><p>Invoice: {invoice_number}</p>"
#             })
#             logger.info(f"Payment receipt sent successfully to {to_email}")
#             return True
#         except Exception as e:
#             logger.error(f"Failed to send payment receipt to {to_email}: {e}")
#             return False
