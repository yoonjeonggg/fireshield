"""SlidingWindowRateLimiter / client_ip 단위 테스트."""

from types import SimpleNamespace

from app.core.config import settings
from app.core.rate_limit import SlidingWindowRateLimiter, client_ip


def test_allows_up_to_limit_then_blocks():
    limiter = SlidingWindowRateLimiter(window_seconds=60)
    assert limiter.hit("a", limit=3, now=0) is None
    assert limiter.hit("a", limit=3, now=1) is None
    assert limiter.hit("a", limit=3, now=2) is None

    retry_after = limiter.hit("a", limit=3, now=3)
    # 가장 오래된 요청(0초)이 창을 벗어나는 60초까지 기다려야 한다
    assert retry_after == 57


def test_window_slides_and_frees_capacity():
    limiter = SlidingWindowRateLimiter(window_seconds=60)
    for t in (0, 10, 20):
        limiter.hit("a", limit=3, now=t)
    assert limiter.hit("a", limit=3, now=59) is not None
    # 0초 요청이 만료되면 1건 여유가 생긴다
    assert limiter.hit("a", limit=3, now=60) is None
    assert limiter.hit("a", limit=3, now=61) is not None


def test_blocked_requests_are_not_recorded():
    # 거부된 요청까지 기록하면 계속 두드리는 동안 영원히 풀리지 않는다
    limiter = SlidingWindowRateLimiter(window_seconds=60)
    limiter.hit("a", limit=1, now=0)
    for t in range(1, 50):
        assert limiter.hit("a", limit=1, now=t) is not None
    assert limiter.hit("a", limit=1, now=60) is None


def test_keys_are_independent():
    limiter = SlidingWindowRateLimiter(window_seconds=60)
    limiter.hit("a", limit=1, now=0)
    assert limiter.hit("a", limit=1, now=1) is not None
    assert limiter.hit("b", limit=1, now=1) is None


def _request(host, forwarded=None):
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


def test_client_ip_ignores_forwarded_header_by_default(monkeypatch):
    monkeypatch.setattr(settings, "trust_forwarded_for", False)
    assert client_ip(_request("1.1.1.1", "9.9.9.9")) == "1.1.1.1"


def test_client_ip_uses_last_forwarded_hop_when_trusted(monkeypatch):
    monkeypatch.setattr(settings, "trust_forwarded_for", True)
    # 앞쪽 값(6.6.6.6)은 클라이언트가 위조할 수 있으므로 프록시가 덧붙인 마지막 값을 쓴다
    assert client_ip(_request("10.0.0.1", "6.6.6.6, 203.0.113.7")) == "203.0.113.7"
    assert client_ip(_request("10.0.0.1")) == "10.0.0.1"
