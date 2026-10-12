"""Duenne Huelle um growatt_public_api.

- Alle HTTP-Requests laufen durch einen Waechter: Timeout und hartes Stundenlimit
  gelten damit auch fuer versteckte Zusatzaufrufe der Bibliothek.
- Der Cache der Bibliothek ist aus: Bei Rate-Limit wuerde er sonst stillschweigend
  alte Werte liefern, die wir als aktuell veroeffentlichen wuerden.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from growatt_public_api import GrowattApi

from .ratelimit import HourlyLimiter

log = logging.getLogger(__name__)

HTTP_TIMEOUT = 30


class LocalLimitExceeded(Exception):
    """Das eigene Stundenlimit ist erreicht; es wurde nichts gesendet."""


class GuardedRequests:
    """Ersetzt requests.Session.request: Timeout setzen, Limit pruefen, dann senden."""

    def __init__(self, inner: Callable[..., Any], limiter: HourlyLimiter,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._inner = inner
        self._limiter = limiter
        self._clock = clock
        self._lock = threading.Lock()

    def __call__(self, method: str, url: str, **kwargs: Any) -> Any:
        with self._lock:
            if not self._limiter.try_acquire(self._clock()):
                raise LocalLimitExceeded(
                    f"Stundenlimit von {self._limiter.limit} Requests erreicht"
                )
        kwargs.setdefault("timeout", HTTP_TIMEOUT)
        return self._inner(method, url, **kwargs)


def build_api(token: str, limiter: HourlyLimiter, server_url: str = "") -> GrowattApi:
    api = GrowattApi(token=token, server_url=server_url or None, use_cache=False)
    http = api.session.session
    http.request = GuardedRequests(http.request, limiter)
    return api


def to_plain(obj: Any) -> Any:
    """Pydantic-Antwort der Bibliothek in ein dict verwandeln."""
    dump = getattr(obj, "model_dump", None)
    return dump() if callable(dump) else obj


class NoahClient:
    """Je Methode genau ein Aufruf, keine Wiederholung."""

    def __init__(self, api: GrowattApi, device_sn: str) -> None:
        self._noah = api.noah
        self._sn = device_sn

    def energy(self) -> dict:
        return to_plain(self._noah.energy_v4(device_sn=self._sn))

    def details(self) -> dict:
        return to_plain(self._noah.details_v4(device_sn=self._sn))

    def wifi(self) -> dict:
        return to_plain(self._noah.wifi_strength(device_sn=self._sn))

    def firmware(self) -> dict:
        return to_plain(self._noah.firmware_info(device_sn=self._sn))
