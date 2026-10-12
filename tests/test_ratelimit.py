from noah_bridge.client import GuardedRequests, LocalLimitExceeded
from noah_bridge.ratelimit import Backoff, HourlyLimiter

import pytest


def test_limiter_blocks_after_limit_and_recovers():
    lim = HourlyLimiter(3)
    assert all(lim.try_acquire(t) for t in (0, 10, 20))
    assert not lim.try_acquire(30)
    assert lim.wait_time(30) == pytest.approx(3570)
    assert lim.try_acquire(3600)  # erster Eintrag ist aus dem Fenster
    assert not lim.try_acquire(3601)


def test_backoff_doubles_and_caps_and_resets():
    b = Backoff(60, 300)
    assert [b.failure() for _ in range(5)] == [60, 120, 240, 300, 300]
    b.success()
    assert b.failure() == 60


def test_guard_sets_timeout_and_enforces_limit():
    calls = []
    guard = GuardedRequests(lambda m, u, **kw: calls.append((m, u, kw)) or "ok",
                            HourlyLimiter(2), clock=lambda: 0.0)
    assert guard("GET", "u1") == "ok"
    guard("GET", "u2")
    assert calls[0][2]["timeout"] == 30
    with pytest.raises(LocalLimitExceeded):
        guard("GET", "u3")
    assert len(calls) == 2  # der dritte Request wurde nie gesendet
