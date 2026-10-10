from typing import Protocol


class VerificationCodeSender(Protocol):
    """Minimum contract required by the authentication feature."""

    def send_verification_code(self, recipient_email: str, code: str) -> None:
        """Deliver a raw verification code without persisting it."""
