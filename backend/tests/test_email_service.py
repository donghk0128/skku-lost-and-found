"""Verify delivery mode selection and prevent a console fallback on SMTP failure."""
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.errors import ApiError
from app.email import service
from app.email.console_client import ConsoleEmailClient
from app.email.smtp_client import SmtpEmailClient


def test_delivery_defaults_to_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMAIL_DELIVERY_MODE", raising=False)
    settings = Settings(_env_file=None, database_url="sqlite://", jwt_secret_key="test-only-secret")
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    assert isinstance(service.EmailService().sender, SmtpEmailClient)


def test_console_requires_explicit_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(email_delivery_mode="console"))
    assert isinstance(service.EmailService().sender, ConsoleEmailClient)


def test_smtp_failure_never_falls_back_to_console(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(email_delivery_mode="smtp"))

    def fail(self, email, code):
        raise ApiError(503, "email_delivery_failed", "Delivery failed")

    def unexpected_console(self, email, code):
        pytest.fail("SMTP failure must not fall back to console delivery")

    monkeypatch.setattr(SmtpEmailClient, "send_verification_code", fail)
    monkeypatch.setattr(ConsoleEmailClient, "send_verification_code", unexpected_console)
    with pytest.raises(ApiError) as error:
        service.EmailService().send_verification_code("recipient@skku.edu", "123456")
    assert error.value.code == "email_delivery_failed"
    assert "123456" not in caplog.text
