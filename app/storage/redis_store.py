"""
Redis cache store with automatic in-memory dictionary fallback.
"""

import json
import logging
from typing import Optional, Any
import redis

from app.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

logger = logging.getLogger(__name__)


class CacheStore:
    def __init__(self):
        self._memory_store: dict = {}
        self._redis: Optional[redis.Redis] = None
        self._is_redis_available = False
        self._init_redis()

    def _init_redis(self):
        try:
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                socket_connect_timeout=0.5,
                decode_responses=True,
            )
            r.ping()
            self._redis = r
            self._is_redis_available = True
            logger.info("Connected to Redis cache successfully.")
        except Exception:
            self._is_redis_available = False
            logger.info("Redis not available; using in-memory dictionary fallback.")

    def get(self, key: str) -> Optional[Any]:
        if self._is_redis_available and self._redis:
            try:
                val = self._redis.get(key)
                if val:
                    return json.loads(val)
                return None
            except Exception:
                self._is_redis_available = False
        return self._memory_store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        if self._is_redis_available and self._redis:
            try:
                self._redis.setex(key, ttl_seconds, json.dumps(value))
                return
            except Exception:
                self._is_redis_available = False
        self._memory_store[key] = value

    def delete(self, key: str):
        if self._is_redis_available and self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._memory_store.pop(key, None)

    def is_redis(self) -> bool:
        return self._is_redis_available


store = CacheStore()
