import time

from fastapi import HTTPException, Request

_buckets: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "local"


def hit(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    recent = [stamp for stamp in _buckets.get(key, []) if now - stamp < window_seconds]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again shortly.")
    recent.append(now)
    _buckets[key] = recent


def reset_limits() -> None:
    _buckets.clear()
