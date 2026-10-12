"""Alert email: a local SMTP server (aiosmtpd) and an smtplib sender.

Concept: SMTP at the application layer. The sender opens a TCP connection to the
mail server and exchanges commands (EHLO, MAIL FROM, RCPT TO, DATA) to deliver a
message. HIGH and CRITICAL alerts are emailed to the analyst; the local server
keeps received messages in an inbox the dashboard shows.
"""

import asyncio
import email
import logging
import queue
import smtplib
import threading
import time
from datetime import datetime
from email.message import EmailMessage
from email.policy import default as default_policy
from typing import Any

from aiosmtpd.controller import Controller

from soc.detector import Alert

logger = logging.getLogger("services.mail")

EMAILED_SEVERITIES = ("HIGH", "CRITICAL")
INBOX_LIMIT = 100
SMTP_TIMEOUT_S = 10


class Inbox:
    """Messages received by the local SMTP server, newest first."""

    def __init__(self) -> None:
        """Start empty."""
        self._lock = threading.Lock()
        self._messages: list[dict[str, Any]] = []
        self._next_id = 1

    def add(self, sender: str, recipient: str, subject: str, body: str) -> None:
        """Store one received message."""
        with self._lock:
            message = {
                "id": self._next_id,
                "received_at": round(time.time(), 3),
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "body": body,
            }
            self._next_id += 1
            self._messages.insert(0, message)
            del self._messages[INBOX_LIMIT:]

    def messages(self) -> list[dict[str, Any]]:
        """Copies of the stored messages."""
        with self._lock:
            return [dict(message) for message in self._messages]


class InboxHandler:
    """aiosmtpd handler: called once a client has sent the DATA of a message."""

    def __init__(self, inbox: Inbox) -> None:
        """Deliver every received message into ``inbox``."""
        self.inbox = inbox

    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:
        """Parse the message and store it; reply with SMTP code 250 (OK)."""
        message = email.message_from_bytes(envelope.content, policy=default_policy)
        body = message.get_body(preferencelist=("plain",))
        self.inbox.add(
            sender=envelope.mail_from,
            recipient=", ".join(envelope.rcpt_tos),
            subject=str(message.get("Subject", "(no subject)")),
            body=body.get_content() if body is not None else "",
        )
        logger.info("SMTP server received a message for %s", envelope.rcpt_tos)
        return "250 Message accepted for delivery"


class MailServer:
    """Local SMTP server on the host and port from ``services.smtp``."""

    def __init__(self, smtp_config: dict[str, Any], inbox: Inbox) -> None:
        """Prepare the server; it binds when started."""
        # aiosmtpd runs on asyncio; we own the event loop so stop() can close it.
        self._loop = asyncio.new_event_loop()
        self._controller = Controller(
            InboxHandler(inbox),
            loop=self._loop,
            hostname=smtp_config["host"],
            port=smtp_config["port"],
        )

    def start(self) -> None:
        """Start the SMTP server in its own thread."""
        self._controller.start()

    def stop(self) -> None:
        """Stop the SMTP server and close its event loop."""
        self._controller.stop()
        self._loop.close()


def alert_email(alert: Alert, smtp_config: dict[str, Any]) -> EmailMessage:
    """Build the email for one alert."""
    message = EmailMessage()
    message["From"] = smtp_config["sender"]
    message["To"] = smtp_config["recipient"]
    message["Subject"] = f"[{alert.severity}] {alert.title}"
    raised = datetime.fromtimestamp(alert.ts).strftime("%Y-%m-%d %H:%M:%S")
    message.set_content(
        f"Severity: {alert.severity}\n"
        f"Rule:     {alert.rule}\n"
        f"Source:   {alert.source}\n"
        f"Raised:   {raised}\n\n"
        f"{alert.detail}\n\n"
        "Sent automatically by SOC Monitor.\n"
    )
    return message


def send_email(message: EmailMessage, smtp_config: dict[str, Any]) -> None:
    """Deliver one message with smtplib (one SMTP session)."""
    with smtplib.SMTP(
        smtp_config["host"], smtp_config["port"], timeout=SMTP_TIMEOUT_S
    ) as smtp:
        smtp.send_message(message)


class AlertMailer:
    """Emails HIGH/CRITICAL alerts from a background thread.

    The detector must never wait on SMTP, so alerts go into a queue and one worker
    thread sends them.
    """

    def __init__(self, smtp_config: dict[str, Any]) -> None:
        """Remember where to send mail."""
        self.smtp_config = smtp_config
        self._queue: queue.Queue[Alert | None] = queue.Queue()
        self._thread = threading.Thread(target=self._work, name="mailer", daemon=True)
        self.sent = 0

    def start(self) -> None:
        """Start the sending thread."""
        self._thread.start()

    def stop(self) -> None:
        """Finish queued mail, then stop the thread."""
        self._queue.put(None)
        self._thread.join(timeout=10)

    def on_alert(self, alert: Alert) -> None:
        """AlertStore listener: queue the alert if it is serious enough."""
        if alert.severity in EMAILED_SEVERITIES:
            self._queue.put(alert)

    def _work(self) -> None:
        """Send queued alerts until the stop marker (None) arrives."""
        while True:
            alert = self._queue.get()
            if alert is None:
                return
            try:
                send_email(alert_email(alert, self.smtp_config), self.smtp_config)
                self.sent += 1
                logger.info("Emailed alert: %s", alert.title)
            except (OSError, smtplib.SMTPException) as error:
                logger.warning("Could not email alert %s: %s", alert.title, error)
