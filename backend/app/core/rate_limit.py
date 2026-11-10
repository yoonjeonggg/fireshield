"""클라이언트 식별과 /verify 요청 횟수 제한.

외부 의존성 없이 프로세스 메모리에서 동작하는 슬라이딩 윈도우 제한기다.
워커를 여러 개 띄우면 워커마다 따로 센다(한도가 워커 수만큼 느슨해짐) —
단일 인스턴스 운영 기준으로는 충분하고, 여러 인스턴스가 되면 Redis 등으로 교체한다.
"""

import time
from collections import deque

from fastapi import HTTPException, Request

from app.core.config import settings

_WINDOW_SECONDS = 60.0
# 키(IP)가 이 수를 넘게 쌓이면 만료된 키를 한 번에 정리해 메모리 증가를 막는다
_MAX_TRACKED_KEYS = 10_000


def client_ip(request: Request) -> str:
    """요청한 클라이언트의 IP. 신뢰하는 프록시 뒤라면 X-Forwarded-For를 따른다."""
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # 프록시는 자신이 본 접속 IP를 맨 뒤에 덧붙인다. 앞쪽 값은 클라이언트가 위조할 수 있다.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class SlidingWindowRateLimiter:
    def __init__(self, window_seconds: float = _WINDOW_SECONDS):
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, limit: int, now: float | None = None) -> float | None:
        """요청 1건을 기록한다. 허용되면 None, 한도 초과면 다시 시도할 수 있기까지 남은 초를 반환."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window_seconds

        if len(self._hits) > _MAX_TRACKED_KEYS:
            self._evict_stale(cutoff)

        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= limit:
            return hits[0] + self.window_seconds - now

        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()

    def _evict_stale(self, cutoff: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in stale:
            del self._hits[key]


verify_limiter = SlidingWindowRateLimiter()


async def enforce_verify_rate_limit(request: Request) -> None:
    """/verify 라우트 의존성 — 한도를 넘으면 429와 Retry-After를 돌려준다."""
    limit = settings.verify_rate_limit_per_minute
    if limit <= 0:
        return

    retry_after = verify_limiter.hit(client_ip(request), limit)
    if retry_after is not None:
        seconds = max(1, int(retry_after + 0.999))
        raise HTTPException(
            status_code=429,
            detail=f"요청이 너무 많습니다. {seconds}초 후 다시 시도해주세요.",
            headers={"Retry-After": str(seconds)},
        )
