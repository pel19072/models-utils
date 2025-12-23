from database_utils.services.email_service import EmailService, MockEmailService
import os

_email_service: EmailService = None


def get_email_service() -> EmailService:
    """Dependency to get email service instance"""
    global _email_service

    if _email_service is None:
        email_provider = os.getenv("EMAIL_PROVIDER", "mock")

        if email_provider == "mock":
            _email_service = MockEmailService()
        # Future Resend integration:
        # elif email_provider == "resend":
        #     from database_utils.services.email_service import ResendEmailService
        #     api_key = os.getenv("RESEND_API_KEY")
        #     if not api_key:
        #         raise ValueError("RESEND_API_KEY environment variable is required for resend provider")
        #     _email_service = ResendEmailService(api_key=api_key)
        else:
            # Fallback to mock if unknown provider
            _email_service = MockEmailService()

    return _email_service
