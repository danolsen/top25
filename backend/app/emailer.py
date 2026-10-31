import smtplib
from email.message import EmailMessage

from app.config import get_settings

outbox: list[dict[str, str]] = []


def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if settings.email_outbox:
        outbox.append({"to": to, "subject": subject, "body": body})
    if not settings.smtp_host:
        return
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.send_message(message)
    except OSError:
        if settings.email_outbox:
            return
        raise


def reset_outbox() -> None:
    outbox.clear()
