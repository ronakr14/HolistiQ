# plugins/logging.py
from plugins.base import Plugin
import logging

logger = logging.getLogger("cli2api")

class LoggingPlugin(Plugin):
    def before_request(self, request, config, kwargs):
        logger.info(f"{request.method} {request.url} | {kwargs}")
        return kwargs

register_plugin("logging", LoggingPlugin())