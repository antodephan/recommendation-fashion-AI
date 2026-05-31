"""SMTP email sender (best-effort, logs in dev)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings
from app.core.logger import logger


class EmailService:
    async def send(self, to: str, subject: str, body: str, html: str | None = None) -> None:
        if not settings.SMTP_HOST:
            logger.info(f"[EMAIL DEV] To: {to} | Subject: {subject}\n{body}")
            return

        msg = EmailMessage()
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
                smtp.starttls()
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
            logger.info(f"Email sent to {to}: {subject}")
        except Exception as exc:
            logger.warning(f"Email send failed: {exc}")
