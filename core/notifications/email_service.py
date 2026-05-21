# email_service.py
from core.data.models.infrastructure.messaging import EmailMessageModel
from core.infrastructure.observability.logging.logging_util import get_logger
from core.infrastructure.messaging.email.registry import get_provider

logger = get_logger(__name__)


class EmailService:
    @staticmethod
    def send(
        to_list,
        subject,
        body,
        cc_list=None,
        bcc_list=None,
        attachments=None,
        notification=False,
        mode="resend",
    ):
        logger.info(f"Email send requested via provider: {mode}")

        message = EmailMessageModel(
            to=to_list,
            subject=subject,
            body=body,
            cc=cc_list or [],
            bcc=bcc_list or [],
            attachments=attachments or [],
            notification=notification,
        )

        provider = get_provider(mode)
        success = provider.send(message)

        if success:
            logger.info("Email sent successfully.")
        else:
            logger.error("Email sending failed.")

        return success