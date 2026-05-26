from notifypy import Notify
from custom_logger.logging_util import get_logger

logger = get_logger(__name__)


def notify_msg(message: str, title: str = 'Automation Update', app: str = 'HolistiQ'):
    logger.info("Sending Notification")
    notification = Notify()
    notification.application_name = app
    notification.title = title
    notification.message = message

    notification.send()
    logger.info("Notification Sent")