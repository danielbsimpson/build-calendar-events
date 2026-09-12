"""Send calendar invites over SMTP as .ics attachments."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import EmailConfig
from .models import Event


class EmailSender:
    """Emails .ics invites to the configured recipient."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def send(self, event: Event, ics_path: str | Path) -> None:
        """Send a single event invite with the .ics file attached."""
        ics_path = Path(ics_path)
        message = self._build_message(event, ics_path)
        self._deliver(message)

    def _build_message(self, event: Event, ics_path: Path) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"{self.config.subject_prefix}{event.title}"
        msg["From"] = self.config.from_addr
        msg["To"] = self.config.to

        body_lines = [event.title, "", f"Starts: {event.start.isoformat()}"]
        if event.location:
            body_lines.append(f"Location: {event.location}")
        if event.url:
            body_lines.append(f"More info: {event.url}")
        msg.set_content("\n".join(body_lines))

        ics_content = ics_path.read_text(encoding="utf-8")
        msg.add_attachment(
            ics_content.encode("utf-8"),
            maintype="text",
            subtype="calendar",
            filename=ics_path.name,
            params={"method": "PUBLISH", "name": ics_path.name},
        )
        return msg

    def _deliver(self, message: EmailMessage) -> None:
        smtp = self.config.smtp
        with smtplib.SMTP(smtp.host, smtp.port) as server:
            if smtp.use_tls:
                server.starttls()
            if smtp.username and smtp.password:
                server.login(smtp.username, smtp.password)
            server.send_message(message)
