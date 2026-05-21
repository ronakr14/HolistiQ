# providers/resend_provider.py
import os
import resend

from core.infrastructure.messaging.email.providers.provider import BaseEmailProvider
from core.data.models.infrastructure.messaging import EmailMessageModel
from core.infrastructure.messaging.email.email_utils import is_html
from core.infrastructure.observability.logging.logging_util import get_logger

logger = get_logger(__name__)


class ResendProvider(BaseEmailProvider):
    def send(self, message: EmailMessageModel) -> bool:
        logger.info("Sending email via Resend.")

        api_key = (
            os.getenv("RESEND_NOTIFICATION_API_KEY")
            if message.notification
            else os.getenv("RESEND_API_KEY")
        )

        if not api_key:
            raise EnvironmentError("Resend API key missing.")

        resend.api_key = api_key

        params = {
            "from": "notification@resend.dev",
            "to": message.to,
            "subject": message.subject,
            "cc": message.cc,
            "bcc": message.bcc,
        }

        if is_html(message.body):
            params["html"] = message.body
        else:
            params["text"] = message.body

        try:
            resend.Emails.send(params)
            logger.info("Resend email sent successfully.")
            return True
        except Exception:
            logger.exception("Resend send failed.")
            return False