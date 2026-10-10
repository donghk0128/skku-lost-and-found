import logging

logger = logging.getLogger(__name__)


class ConsoleEmailClient:
    """Development-only sender that writes the code to the local server console."""

    def send_verification_code(self, recipient_email: str, code: str) -> None:
        logger.warning("[DEV EMAIL] recipient=%s verification_code=%s", recipient_email, code)
