"""Exercise SMTP delivery without making network calls or sending real email."""
import smtplib
from types import SimpleNamespace

import pytest

from app.core.errors import ApiError
from app.email import smtp_client


@pytest.fixture()
def settings(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    config = SimpleNamespace(
        smtp_host="smtp.example.test", smtp_port=587,
        smtp_username="sender@example.test", smtp_password="test-only-password",
        smtp_from_email="sender@example.test", smtp_from_name="찾자", smtp_use_tls=True,
    )
    monkeypatch.setattr(smtp_client, "get_settings", lambda: config)
    return config


def test_smtp_starttls_login_and_verification_message(settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, *, context):
            calls.append("tls")

        def login(self, username, password):
            calls.append((username, password))

        def send_message(self, message):
            calls.append(message)

    monkeypatch.setattr(smtp_client.smtplib, "SMTP", FakeSmtp)
    smtp_client.SmtpEmailClient().send_verification_code("recipient@skku.edu", "123456")
    assert calls[:3] == [(settings.smtp_host, 587, 10), "tls", (settings.smtp_username, settings.smtp_password)]
    message = calls[3]
    assert message["To"] == "recipient@skku.edu"
    assert settings.smtp_from_email in message["From"]
    assert "123456" in message.get_content()


def test_missing_smtp_configuration_is_reported(settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.smtp_from_email = ""

    def unexpected_connection(*args, **kwargs):
        pytest.fail("Unconfigured SMTP must not open a network connection")

    monkeypatch.setattr(smtp_client.smtplib, "SMTP", unexpected_connection)
    with pytest.raises(ApiError) as error:
        smtp_client.SmtpEmailClient().send_verification_code("recipient@skku.edu", "123456")
    assert error.value.status_code == 503
    assert error.value.code == "email_not_configured"


def test_smtp_failure_is_reported_without_credentials(settings: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise smtplib.SMTPAuthenticationError(535, b"credentials rejected")

    monkeypatch.setattr(smtp_client.smtplib, "SMTP", fail)
    with pytest.raises(ApiError) as error:
        smtp_client.SmtpEmailClient().send_verification_code("recipient@skku.edu", "123456")
    assert error.value.code == "email_delivery_failed"
    assert settings.smtp_password not in error.value.message
