# redis_client.py
import redis

redis_client = redis.Redis(host="localhost", port=6379, db=0)


def check_rate_limit(path: str, limit: int, client_ip: str):
    key = f"rate:{client_ip}:{path}"
    current = redis_client.incr(key)

    if current == 1:
        redis_client.expire(key, 60)

    if current > limit:
        raise Exception("Rate limit exceeded")