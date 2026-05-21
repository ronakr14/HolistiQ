from datetime import datetime

from core.infra.observe.logging.logging_util import get_logger
from core.utils.datetime_utils import now_utc_ts

logger = get_logger(__name__)


def generate_datetime_suffix(now: datetime = None) -> str:
    logger.debug("Generating datetime suffix")
    now = now_utc_ts()
    return now.strftime("%Y%m%d%H%M%S")
