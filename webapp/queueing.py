from __future__ import annotations

from redis import Redis
from rq import Queue

from .config import redis_url


def get_redis() -> Redis:
    return Redis.from_url(redis_url())


def get_queue(name: str = "default") -> Queue:
    return Queue(name, connection=get_redis())

