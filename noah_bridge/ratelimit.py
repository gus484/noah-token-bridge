"""Schutz vor Request-Fluten: Stundenlimit und exponentieller Backoff.

Beide Klassen sind frei von I/O und Zeitquellen (Zeit wird uebergeben), damit sie
deterministisch testbar sind.
"""
from __future__ import annotations

from collections import deque


class HourlyLimiter:
    """Gleitendes Fenster: hoechstens `limit` Requests in 3600 Sekunden."""

    WINDOW = 3600.0

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._stamps: deque[float] = deque()

    def _trim(self, now: float) -> None:
        while self._stamps and now - self._stamps[0] >= self.WINDOW:
            self._stamps.popleft()

    def wait_time(self, now: float) -> float:
        """Sekunden bis wieder ein Request erlaubt ist (0 = jetzt)."""
        self._trim(now)
        if len(self._stamps) < self.limit:
            return 0.0
        return self._stamps[0] + self.WINDOW - now

    def try_acquire(self, now: float) -> bool:
        if self.wait_time(now) > 0:
            return False
        self._stamps.append(now)
        return True

    def used(self, now: float) -> int:
        self._trim(now)
        return len(self._stamps)


class Backoff:
    """Verdoppelt die Wartezeit nach jedem Fehler bis `maximum`; Erfolg setzt zurueck."""

    def __init__(self, start: float, maximum: float) -> None:
        self.start = start
        self.maximum = maximum
        self._current = 0.0
        self.failures = 0

    def failure(self) -> float:
        self.failures += 1
        self._current = self.start if self._current == 0 else min(self._current * 2, self.maximum)
        return self._current

    def success(self) -> None:
        self._current = 0.0
        self.failures = 0
