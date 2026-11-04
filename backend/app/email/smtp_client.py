import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.errors import ApiError


class SmtpEmailClient:
    """Provider-independent SMTP implementation for transactional emails."""

    def send_verification_code(self, recipient_email: str, code: str) -> None:
        settings = get_settings()
        if (
            not settings.smtp_host
            or not settings.smtp_from_email
            or bool(settings.smtp_username) != bool(settings.smtp_password)
        ):
            raise ApiError(503, "email_not_configured", "SMTP 이메일 발송 서비스가 아직 설정되지 않았습니다.")

        message = EmailMessage()
        message["Subject"] = "[SKKU FINDER] 이메일 인증 코드 / Email verification code"
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = recipient_email
        expiry_minutes = settings.email_verification_expire_minutes
        message.set_content(
            "SKKU FINDER 이메일 인증 코드입니다.\n"
            "Your SKKU FINDER email verification code is:\n\n"
            f"{code}\n\n"
            f"인증 코드는 {expiry_minutes}분 동안 유효합니다.\n"
            f"This code is valid for {expiry_minutes} minutes.\n\n"
            "요청하지 않은 메일이라면 무시해주세요.\n"
            "If you did not request this email, please ignore it."
        )

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
                if settings.smtp_use_tls:
                    client.starttls(context=ssl.create_default_context())
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise ApiError(503, "email_delivery_failed", "인증 이메일을 보낼 수 없습니다. 잠시 후 다시 시도해 주세요.") from error
