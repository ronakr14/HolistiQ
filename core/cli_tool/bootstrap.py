import logging

from core.cli_tool.schema import CliContext
from custom_logger.logging_util import setup_logging
from core.utils.datetime_utils import now_ts
from core.utils.uuid_utils import new_uuid


def bootstrap(
    log_level: str | None,
    # config: str | None,
) -> CliContext | None:

    setup_logging(config={"level": log_level})
    logger = logging.getLogger("HolistiQ")

    logger.info("*" * 60)
    logger.info("HolistiQ - All rounder tool")
    logger.info("*" * 60)

    ctx = CliContext(
        run_id=new_uuid(),
        app_start_time=now_ts(),
    )

    logger.debug(f"CliContext initialized: {ctx}")
    return ctx
