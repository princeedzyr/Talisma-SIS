import hashlib
import re

from wingman_ai.config.settings import get_wingman_settings


WINDOW_SECONDS = 60
RATE_LIMIT_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if ARGV[3] == '1' and redis.call('EXISTS', KEYS[2]) == 1 then
    return {0, current, redis.call('TTL', KEYS[1]), 1}
end
if current >= tonumber(ARGV[1]) then
    return {1, current, redis.call('TTL', KEYS[1]), 0}
end
if ARGV[3] == '1' then
    redis.call('SET', KEYS[2], '1', 'EX', ARGV[2])
end
current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return {0, current, redis.call('TTL', KEYS[1]), 0}
"""


def check_rate_limit(user, conversation_id=None, request_id=None):
    try:
        import frappe
    except Exception:
        return {"allowed": True}

    settings = get_wingman_settings()
    # A user may have Wingman open in more than one tab or workflow. Keeping a
    # single counter per user lets activity in one conversation incorrectly
    # block every other conversation. Scope the short-window limit to the
    # conversation while retaining a safe fallback for older clients.
    scope = str(conversation_id or "default").strip() or "default"
    scope_hash = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:20]
    cache_key = f"wingman_ai:rate:v2:{user or 'Guest'}:{scope_hash}"
    safe_request_id = re.sub(r"[^A-Za-z0-9_-]", "", str(request_id or ""))[:80]
    request_key = f"{cache_key}:request:{safe_request_id or 'none'}"
    cache = frappe.cache()
    try:
        blocked, current, ttl, duplicate = cache.eval(
            RATE_LIMIT_SCRIPT,
            2,
            cache.make_key(cache_key),
            cache.make_key(request_key),
            settings.rate_limit_per_minute,
            WINDOW_SECONDS,
            1 if safe_request_id else 0,
        )
    except Exception:
        # Availability is more important than throttling when the cache is
        # temporarily unavailable; business permissions still apply.
        return {"allowed": True, "limit": settings.rate_limit_per_minute}

    retry_after = max(int(ttl or 0), 1) if blocked else 0
    if blocked:
        return {
            "allowed": False,
            "message": f"Wingman reached the request limit for this conversation. Please try again in {retry_after} seconds.",
            "limit": settings.rate_limit_per_minute,
            "current": int(current or 0),
            "retry_after_seconds": retry_after,
        }
    return {
        "allowed": True,
        "limit": settings.rate_limit_per_minute,
        "current": int(current or 0),
        "duplicate": bool(duplicate),
    }
