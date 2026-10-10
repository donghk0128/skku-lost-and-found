import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.errors import ApiError


class SmtpEmailClient:
    """Provider-independent SMTP implementation for transactional emails."""

    def send_verification_code(self, recipient_email: str, code: str) -> None:
        settings = get_settings()
        if not settings.smtp_host or not settings.smtp_from_email:
            raise ApiError(503, "email_not_configured", "SMTP 이메일 발송 서비스가 아직 설정되지 않았습니다.")

        message = EmailMessage()
        message["Subject"] = "[찾자] 성균관대학교 이메일 인증 코드"
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = recipient_email
        message.set_content(
            f"성균관대학교 분실물 찾기 서비스 찾자의 인증 코드입니다.\n\n{code}\n\n인증 코드는 5분 동안 유효합니다."
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
