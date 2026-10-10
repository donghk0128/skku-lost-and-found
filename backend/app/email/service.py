from app.core.config import get_settings
from app.core.errors import ApiError
from app.email.console_client import ConsoleEmailClient
from app.email.protocols import VerificationCodeSender
from app.email.smtp_client import SmtpEmailClient


class EmailService:
    """Selects an email delivery implementation without coupling auth to a provider."""

    def __init__(self, sender: VerificationCodeSender | None = None):
        self.sender = sender or self._sender_for_configured_mode()

    def send_verification_code(self, recipient_email: str, code: str) -> None:
        self.sender.send_verification_code(recipient_email, code)

    @staticmethod
    def _sender_for_configured_mode() -> VerificationCodeSender:
        mode = get_settings().email_delivery_mode.lower()
        if mode == "console":
            return ConsoleEmailClient()
        if mode == "smtp":
            return SmtpEmailClient()
        raise ApiError(500, "invalid_email_delivery_mode", "EMAIL_DELIVERY_MODE 설정값이 올바르지 않습니다.")
