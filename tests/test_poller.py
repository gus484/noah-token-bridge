from noah_bridge.client import LocalLimitExceeded
from noah_bridge.poller import Poller, Task
from noah_bridge.ratelimit import HourlyLimiter


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(tasks, limiter=None, clock=None):
    clock = clock or Clock()
    avail = []
    p = Poller(tasks, limiter or HourlyLimiter(100), 60, 1800, avail.append, clock=clock)
    p.schedule_start(stagger=0)
    return p, clock, avail


def drive(p, clock, seconds):
    """Treibt den Poller in 1-s-Schritten voran."""
    end = clock.now + seconds
    while clock.now < end:
        wait = p.step()
        clock.now += max(min(wait, 1.0), 0.1)


def test_runs_task_at_interval_and_marks_available():
    runs = []
    t = Task("energy", 300, lambda: runs.append(1), primary=True)
    p, clock, avail = make([t])
    drive(p, clock, 1000)
    assert len(runs) == 4  # bei 0, 300, 600, 900 s
    assert avail[0] is True


def test_failure_backs_off_exponentially_never_immediately():
    attempts = []

    def boom():
        attempts.append(clock.now)
        raise RuntimeError("down")

    t = Task("energy", 300, boom, primary=True)
    p, clock, avail = make([t])
    start = clock.now
    drive(p, clock, 3000)
    gaps = [b - a for a, b in zip(attempts, attempts[1:])]
    assert gaps[0] >= 60 and gaps[1] >= 120 and gaps[2] >= 240  # verdoppelt sich
    assert all(g >= 60 for g in gaps)
    assert len(attempts) <= 7
    assert avail and avail[-1] is False


def test_recovery_resets_backoff_and_sets_online():
    state = {"fail": True}

    def flaky():
        if state["fail"]:
            raise RuntimeError("x")

    t = Task("energy", 300, flaky, primary=True)
    p, clock, avail = make([t])
    drive(p, clock, 100)
    state["fail"] = False
    drive(p, clock, 400)
    assert avail[0] is False and avail[-1] is True
    assert t.backoff.failures == 0


def test_secondary_failure_does_not_mark_offline():
    t1 = Task("energy", 300, lambda: None, primary=True)
    t2 = Task("wifi", 300, lambda: (_ for _ in ()).throw(RuntimeError("x")))
    p, clock, avail = make([t1, t2])
    drive(p, clock, 50)
    assert False not in avail


def test_hourly_limit_stops_requests():
    runs = []
    lim = HourlyLimiter(2)

    def run():
        lim.try_acquire(clock.now)
        runs.append(1)

    t = Task("energy", 60, run, primary=True)
    p, clock, _ = make([t], limiter=lim)
    drive(p, clock, 1200)
    assert len(runs) == 2


def test_local_limit_error_is_not_a_failure():
    def limited():
        raise LocalLimitExceeded("x")

    t = Task("energy", 300, limited, primary=True)
    p, clock, avail = make([t])
    drive(p, clock, 30)
    assert t.backoff.failures == 0 and avail == []


def test_min_gap_between_requests():
    stamps = []
    tasks = [Task(n, 300, lambda: stamps.append(clock.now)) for n in "abc"]
    p, clock, _ = make(tasks)
    drive(p, clock, 30)
    assert all(b - a >= 5 for a, b in zip(stamps, stamps[1:]))


def test_describe_error_is_short_for_network_problems():
    import logging

    import requests

    from noah_bridge.poller import describe_error

    dns = requests.ConnectionError("HTTPSConnectionPool(...) NameResolutionError getaddrinfo failed")
    level, text = describe_error(dns)
    assert level == logging.WARNING and "DNS" in text and "HTTPSConnectionPool" not in text
    assert describe_error(requests.Timeout("x"))[0] == logging.WARNING
    assert describe_error(requests.ConnectionError("reset"))[1].endswith("(Verbindung fehlgeschlagen)")
    level, text = describe_error(ValueError("kaputt"))
    assert level == logging.ERROR and "ValueError: kaputt" in text
