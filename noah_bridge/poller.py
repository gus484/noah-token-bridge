"""Polling-Schleife: je Schritt hoechstens ein Task, kein Retry, kein sofortiger Neuversuch.

Fehler setzen die Faelligkeit des betroffenen Tasks per Backoff nach hinten. Zwischen zwei
Requests liegt immer mindestens `min_gap` Sekunden. Zeit und Warten werden injiziert.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import requests

from .client import LocalLimitExceeded
from .ratelimit import Backoff, HourlyLimiter

log = logging.getLogger(__name__)


def describe_error(exc: Exception) -> tuple[int, str]:
    """(Log-Level, Kurztext). Netzfehler sind erwartbar und brauchen keine lange Exception-Zeile."""
    if isinstance(exc, requests.Timeout):
        return logging.WARNING, "Growatt nicht erreichbar (Zeitueberschreitung)"
    if isinstance(exc, requests.ConnectionError):
        text = str(exc)
        if "NameResolutionError" in text or "getaddrinfo" in text:
            return logging.WARNING, "Growatt nicht erreichbar (DNS, vermutlich kein Netz)"
        return logging.WARNING, "Growatt nicht erreichbar (Verbindung fehlgeschlagen)"
    return logging.ERROR, f"{type(exc).__name__}: {exc}"


@dataclass
class Task:
    name: str
    interval: float
    run: Callable[[], None]  # holt, parst und veroeffentlicht; wirft bei Fehlern
    due: float = 0.0
    backoff: Backoff | None = None
    primary: bool = False  # steuert die Verfuegbarkeit (online/offline)
    ok: bool | None = field(default=None, init=False)


class Poller:
    def __init__(
        self,
        tasks: list[Task],
        limiter: HourlyLimiter,
        backoff_start: float,
        backoff_max: float,
        set_available: Callable[[bool], None],
        clock: Callable[[], float] = time.monotonic,
        min_gap: float = 5.0,
    ) -> None:
        self.tasks = tasks
        self.limiter = limiter
        self.set_available = set_available
        self.clock = clock
        self.min_gap = min_gap
        self._next_request = 0.0
        self._limit_logged = False
        for t in tasks:
            t.backoff = Backoff(backoff_start, backoff_max)

    def schedule_start(self, stagger: float = 10.0) -> None:
        """Verteilt die ersten Abrufe, damit nicht alles gleichzeitig startet."""
        now = self.clock()
        for i, t in enumerate(self.tasks):
            t.due = now + i * stagger

    def step(self) -> float:
        """Fuehrt hoechstens einen Request-Task aus; liefert die Wartezeit bis zum naechsten Schritt."""
        now = self.clock()
        if now < self._next_request:
            return self._next_request - now
        task = min(self.tasks, key=lambda t: t.due)
        if task.due > now:
            return task.due - now
        wait = self.limiter.wait_time(now)
        if wait > 0:
            if not self._limit_logged:
                log.warning("Stundenlimit erreicht, pausiere %.0f s", wait)
                self._limit_logged = True
            return wait
        self._limit_logged = False

        try:
            task.run()
        except LocalLimitExceeded:
            task.due = self.clock() + max(self.limiter.wait_time(self.clock()), self.min_gap)
            log.warning("%s: Stundenlimit erreicht, zurueckgestellt", task.name)
            return self.min_gap
        except Exception as exc:  # bewusst breit: der Prozess darf nie abstuerzen
            delay = task.backoff.failure()
            t = self.clock()
            task.due = t + delay
            self._next_request = t + self.min_gap
            task.ok = False
            level, text = describe_error(exc)
            log.log(level, "%s fehlgeschlagen (%d. Fehler in Folge, naechster Versuch in %.0f s): %s",
                    task.name, task.backoff.failures, delay, text)
            if task.primary:
                self.set_available(False)
            return self.min_gap

        t = self.clock()
        task.backoff.success()
        task.due = t + task.interval
        self._next_request = t + self.min_gap
        if task.ok is False:
            log.info("%s: wieder erfolgreich", task.name)
        task.ok = True
        if task.primary:
            self.set_available(True)
        return self.min_gap

    def run_forever(self, stop: threading.Event, sleep: Callable[[float], bool] | None = None) -> None:
        sleep = sleep or stop.wait
        self.schedule_start()
        while not stop.is_set():
            wait = self.step()
            sleep(min(max(wait, 0.5), 60.0))
