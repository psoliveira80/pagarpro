from typing import Protocol, runtime_checkable


@runtime_checkable
class IEmailSender(Protocol):
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None: ...
