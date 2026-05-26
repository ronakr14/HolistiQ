# plugins/rate_limit.py
from plugins.base import Plugin
from redis_client import redis_client

class RateLimitPlugin(Plugin):
    def before_request(self, request, config, kwargs):
        limit = config.get("rate_limit", 10)
        key = f"rate:{request.client.host}:{config['name']}"

        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 60)

        if count > limit:
            raise Exception("Rate limit exceeded")

        return kwargs

register_plugin("rate_limit", RateLimitPlugin())