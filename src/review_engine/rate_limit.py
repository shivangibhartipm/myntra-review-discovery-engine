from __future__ import annotations

import time


class RateLimiter:
    def __init__(self, rps: float, sleeper=time.sleep, clock=time.monotonic) -> None:
        self.min_interval = (1.0 / rps) if rps and rps > 0 else 0.0
        self._sleeper = sleeper
        self._clock = clock
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = self._clock()
        delay = self.min_interval - (now - self._last)
        if delay > 0:
            self._sleeper(delay)
        self._last = self._clock()
