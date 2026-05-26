# idempotency.py
import json
from redis_client import redis_client

TTL = 60 * 60 * 24  # 24 hours

def get_key(key: str):
    data = redis_client.get(f"idempotency:{key}")
    return json.loads(data) if data else None

def set_processing(key: str):
    redis_client.setex(
        f"idempotency:{key}",
        TTL,
        json.dumps({"status": "processing"})
    )

def set_completed(key: str, response):
    redis_client.setex(
        f"idempotency:{key}",
        TTL,
        json.dumps({
            "status": "completed",
            "response": response
        })
    )


    # plugins/idempotency.py
from plugins.base import Plugin
from idempotency import get_key, set_processing, set_completed

class IdempotencyPlugin(Plugin):
    def before_request(self, request, config, kwargs):
        key = request.headers.get("Idempotency-Key")
        if not key:
            return kwargs

        existing = get_key(key)
        if existing:
            if existing["status"] == "completed":
                raise CachedResponse(existing["response"])
            raise Exception("Still processing")

        set_processing(key)
        request.state.idem_key = key
        return kwargs

    def after_response(self, request, response, config):
        key = getattr(request.state, "idem_key", None)
        if key:
            set_completed(key, response)
        return response

register_plugin("idempotency", IdempotencyPlugin())