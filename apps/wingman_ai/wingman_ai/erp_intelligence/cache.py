import json
import time

from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.frappe_adapter import FrappeERPAdapter


LOCAL_CACHE = {}
CACHE_PREFIX = "wingman_ai:erp_intelligence"
CACHE_INDEX_KEY = f"{CACHE_PREFIX}:index"


class ERPKnowledgeCache:
    def __init__(self, adapter=None, config=None):
        self.adapter = adapter or FrappeERPAdapter()
        self.config = config or get_erp_intelligence_config()

    def get(self, key):
        payload = self.read_payload(key)
        if not payload:
            return None
        if self.is_expired(payload):
            self.invalidate(key)
            return None
        return payload.get("value")

    def set(self, key, value):
        payload = {"created_at": time.time(), "ttl": self.config.cache_ttl_seconds, "value": value}
        serialized = json.dumps(payload, default=str)
        cache = self.adapter.get_cache()
        if cache:
            try:
                cache.set_value(self.cache_key(key), serialized, expires_in_sec=self.config.cache_ttl_seconds)
                self.add_to_index(self.cache_key(key))
                return value
            except Exception:
                pass
        LOCAL_CACHE[self.cache_key(key)] = serialized
        self.add_to_index(self.cache_key(key))
        return value

    def get_or_set(self, key, loader):
        value = self.get(key)
        if value is not None:
            return value
        return self.set(key, loader())

    def invalidate(self, key=None):
        if key:
            keys = [self.cache_key(key)]
        else:
            keys = self.read_index()
            keys.extend(cache_key for cache_key in list(LOCAL_CACHE) if cache_key.startswith(CACHE_PREFIX))
            keys = sorted(set(keys))

        deleted = self.delete_cache_keys(keys)

        if not key:
            self.write_index([])

        return {"status": "ok", "invalidated": deleted, "key": key}

    def invalidate_prefix(self, key_prefix):
        cache_prefix = self.cache_key(key_prefix)
        keys = self.read_index()
        keys.extend(cache_key for cache_key in list(LOCAL_CACHE) if cache_key.startswith(CACHE_PREFIX))
        matching_keys = sorted(set(key for key in keys if key.startswith(cache_prefix)))
        deleted = self.delete_cache_keys(matching_keys)
        return {"status": "ok", "invalidated": deleted, "prefix": key_prefix}

    def delete_cache_keys(self, keys):
        cache = self.adapter.get_cache()
        deleted = 0
        for cache_key in keys:
            if cache:
                try:
                    cache.delete_value(cache_key)
                except Exception:
                    pass
            if LOCAL_CACHE.pop(cache_key, None) is not None:
                deleted += 1
            elif cache:
                deleted += 1

        return deleted

    def read_payload(self, key):
        cache_key = self.cache_key(key)
        raw = None
        cache = self.adapter.get_cache()
        if cache:
            try:
                raw = cache.get_value(cache_key)
            except Exception:
                raw = None
        raw = raw if raw is not None else LOCAL_CACHE.get(cache_key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def is_expired(self, payload):
        ttl = int(payload.get("ttl") or self.config.cache_ttl_seconds)
        created_at = float(payload.get("created_at") or 0)
        return ttl > 0 and time.time() - created_at > ttl

    def cache_key(self, key):
        return f"{CACHE_PREFIX}:{key}"

    def add_to_index(self, cache_key):
        index = set(self.read_index())
        index.add(cache_key)
        self.write_index(sorted(index))

    def read_index(self):
        cache = self.adapter.get_cache()
        raw = None
        if cache:
            try:
                raw = cache.get_value(CACHE_INDEX_KEY)
            except Exception:
                raw = None
        raw = raw if raw is not None else LOCAL_CACHE.get(CACHE_INDEX_KEY)
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except ValueError:
            return []
        return value if isinstance(value, list) else []

    def write_index(self, index):
        serialized = json.dumps(index)
        cache = self.adapter.get_cache()
        if cache:
            try:
                cache.set_value(CACHE_INDEX_KEY, serialized, expires_in_sec=self.config.cache_ttl_seconds)
            except Exception:
                pass
        LOCAL_CACHE[CACHE_INDEX_KEY] = serialized


def refresh_metadata_cache():
    config = get_erp_intelligence_config()
    if not config.auto_refresh_enabled:
        return {"status": "skipped", "reason": "auto_refresh_disabled"}

    from wingman_ai.erp_intelligence.service import get_erp_intelligence_service

    service = get_erp_intelligence_service()
    return service.refresh_metadata()
