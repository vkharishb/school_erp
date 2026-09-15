"""Small transactional email service independent of the future Communication module."""
import smtplib
from email.message import EmailMessage
from app.core.config import get_settings


def send_transactional_email(*, to_email: str, subject: str, body: str) -> tuple[bool, str | None]:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        return False, "SMTP is not configured"
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_starttls:
                client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)
        return True, None
    except Exception:  # delivery failure must never roll back the business transaction
        return False, "Email delivery failed"

