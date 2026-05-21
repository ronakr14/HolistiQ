import os
import smtplib
from email.message import EmailMessage

from core.infrastructure.messaging.email.providers.provider import BaseEmailProvider
from core.data.models.infrastructure.messaging import EmailMessageModel
from core.infrastructure.messaging.email.email_utils import is_html, load_attachment
from core.infrastructure.observability.logging.logging_util import get_logger

logger = get_logger(__name__)


class GmailProvider(BaseEmailProvider):
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465

    def send(self, message: EmailMessageModel) -> bool:
        logger.info("Sending email via Gmail.")

        sender = os.getenv("GMAIL_SENDER")
        password = os.getenv("GMAIL_APP_PASSWORD")

        if not sender or not password:
            raise EnvironmentError("Missing Gmail credentials.")

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ", ".join(message.to)
        msg["Subject"] = message.subject

        if message.cc:
            msg["Cc"] = ", ".join(message.cc)

        if is_html(message.body):
            msg.add_alternative(message.body, subtype="html")
        else:
            msg.set_content(message.body)

        # Attachments
        for path in message.attachments or []:
            try:
                data, maintype, subtype = load_attachment(path)
                msg.add_attachment(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=path.split("/")[-1],
                )
                logger.debug(f"Attachment added: {path}")
            except Exception:
                logger.exception(f"Failed to attach: {path}")

        recipients = list(set(message.to + message.cc + message.bcc))

        try:
            with smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT) as server:
                server.login(sender, password)
                server.send_message(msg, from_addr=sender, to_addrs=recipients)
            logger.info("Gmail email sent successfully.")
            return True
        except Exception:
            logger.exception("Gmail send failed.")
            return False