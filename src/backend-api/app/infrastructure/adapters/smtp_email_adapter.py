import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.infrastructure.settings import get_settings

log = structlog.get_logger()


class SmtpEmailAdapter:
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        settings = get_settings()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        def _send() -> None:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

        await asyncio.to_thread(_send)
        log.info("email_sent_smtp", to=to, subject=subject)
