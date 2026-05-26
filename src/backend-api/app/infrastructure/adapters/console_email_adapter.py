import structlog

log = structlog.get_logger()


class ConsoleEmailAdapter:
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        log.info(
            "email_sent_console",
            to=to,
            subject=subject,
            body_text=body_text or "(html only)",
        )
        print(f"\n{'='*60}")
        print(f"TO: {to}")
        print(f"SUBJECT: {subject}")
        print(f"{'='*60}")
        print(body_text or body_html)
        print(f"{'='*60}\n")
