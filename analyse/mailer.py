from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any


def send_email_alert(
    subject: str,
    body: str,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    email_from: str | None = None,
    email_to: str | None = None,
    use_tls: bool | None = None,
) -> None:
    """Send an email notification.

    Parameters
    ----------
    subject : str
        Email subject.
    body : str
        Email message body.
    smtp_host : str | None, optional
        SMTP server hostname, by default read from SMTP_HOST.
    smtp_port : int | None, optional
        SMTP server port, by default read from SMTP_PORT or 587.
    smtp_user : str | None, optional
        SMTP username, by default read from SMTP_USER.
    smtp_password : str | None, optional
        SMTP password, by default read from SMTP_PASSWORD.
    email_from : str | None, optional
        Sender email address, by default read from EMAIL_FROM or SMTP_USER.
    email_to : str | None, optional
        Recipient email address, by default read from EMAIL_TO.
    use_tls : bool | None, optional
        Whether to use TLS for SMTP, by default read from SMTP_USE_TLS.
    """
    smtp_host = smtp_host or os.getenv("SMTP_HOST")
    smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
    smtp_user = smtp_user or os.getenv("SMTP_USER")
    smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
    email_from = email_from or os.getenv("EMAIL_FROM") or smtp_user
    email_to = email_to or os.getenv("EMAIL_TO")
    use_tls = use_tls if use_tls is not None else os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    missing = [
        name
        for name, value in {
            "SMTP_HOST": smtp_host,
            "EMAIL_FROM or SMTP_USER": email_from,
            "EMAIL_TO": email_to,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing email configuration: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_from
    message["To"] = email_to
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)
