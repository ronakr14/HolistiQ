from notifypy import Notify
from core.infrastructure.observability.logging.logging_util import get_logger

logger = get_logger(__name__)


def notify_msg(message: str, title: str = None):
    logger.debug("Sending Notification")
    notification = Notify()
    notification.application_name = "HolistiQ"
    notification.title = "Automation Update"
    if title:
        notification.title = title
    notification.message = message

    notification.send()
    logger.debug("Notification Sent")