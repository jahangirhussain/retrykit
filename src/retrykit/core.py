"""Retry decorator with exponential backoff and full jitter.

Works on plain functions and coroutine functions. Time and randomness are
injectable, so behaviour is deterministic under test.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, Type

RandomFn = Callable[[], float]
OnRetry = Callable[[int, BaseException, float], None]


@dataclass(frozen=True)
class Backoff:
    """Exponential backoff schedule: ``min(cap, base * factor ** attempt)``.

    ``attempt`` is zero-based: the wait after the first failure uses 0.
    """

    base: float = 0.1
    cap: float = 30.0
    factor: float = 2.0

    def __post_init__(self) -> None:
        if self.base <= 0 or self.cap <= 0 or self.factor < 1:
            raise ValueError("base and cap must be > 0 and factor >= 1")

    def ceiling(self, attempt: int) -> float:
        """Upper bound of the wait for ``attempt``, before jitter."""
        return min(self.cap, self.base * self.factor**attempt)

    def delay(self, attempt: int, rng: RandomFn = random.random) -> float:
        """Full jitter: a uniform draw from ``[0, ceiling(attempt))``."""
        return rng() * self.ceiling(attempt)


def retry(
    *,
    attempts: int = 5,
    on: Tuple[Type[BaseException], ...] = (Exception,),
    backoff: Backoff = Backoff(),
    sleep: Optional[Callable[[float], Any]] = None,
    rng: RandomFn = random.random,
    on_retry: Optional[OnRetry] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Retry the wrapped callable when it raises one of the ``on`` exceptions.

    Args:
        attempts: Total tries, including the first. Must be >= 1.
        on: Exception types that trigger a retry; anything else propagates.
        backoff: Wait schedule between tries.
        sleep: Override for ``time.sleep`` (sync) or ``asyncio.sleep`` (async).
        rng: Source of uniform floats in ``[0, 1)``; override for tests.
        on_retry: Called as ``on_retry(attempt, exc, delay)`` before each wait.

    The final exception is re-raised unchanged once attempts are exhausted.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                pause = sleep or asyncio.sleep
                for attempt in range(attempts):
                    try:
                        return await fn(*args, **kwargs)
                    except on as exc:
                        if attempt == attempts - 1:
                            raise
                        delay = backoff.delay(attempt, rng)
                        if on_retry:
                            on_retry(attempt + 1, exc, delay)
                        await pause(delay)

            return async_wrapper

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            pause = sleep or time.sleep
            for attempt in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except on as exc:
                    if attempt == attempts - 1:
                        raise
                    delay = backoff.delay(attempt, rng)
                    if on_retry:
                        on_retry(attempt + 1, exc, delay)
                    pause(delay)

        return wrapper

    return decorator
