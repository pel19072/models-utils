from database_utils.services.email_service import EmailService, MockEmailService
import os

_email_service: EmailService = None


def get_email_service() -> EmailService:
    """Dependency to get email service instance"""
    global _email_service

    if _email_service is None:
        email_provider = os.getenv("EMAIL_PROVIDER", "mock")

        if email_provider == "smtp":
            from database_utils.services.email_service import SMTPEmailService
            _email_service = SMTPEmailService(
                host=os.environ["SMTP_HOST"],
                port=int(os.environ["SMTP_PORT"]),
                username=os.environ["SMTP_USERNAME"],
                password=os.environ["SMTP_PASSWORD"],
                from_address=os.environ["SMTP_FROM_ADDRESS"],
                use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            )
        else:
            _email_service = MockEmailService()

    return _email_service
