from __future__ import annotations

import time
from collections import defaultdict, deque


class DedupeCache:
    def __init__(self, window_seconds: int) -> None:
        self.window_seconds = window_seconds
        self.cache: dict[str, float] = {}

    def seen_recently(self, key: str) -> bool:
        now = time.time()
        expired = [k for k, ts in self.cache.items() if now - ts > self.window_seconds]
        for item in expired:
            self.cache.pop(item, None)
        if key in self.cache:
            return True
        self.cache[key] = now
        return False


class CooldownManager:
    def __init__(self, cooldown_seconds: int) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.last_hit: dict[str, float] = defaultdict(float)

    def in_cooldown(self, key: str) -> bool:
        now = time.time()
        if now - self.last_hit.get(key, 0.0) < self.cooldown_seconds:
            return True
        self.last_hit[key] = now
        return False


class FailureTracker:
    def __init__(self, max_failures: int, cooldown_seconds: int) -> None:
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self.failures: dict[str, int] = defaultdict(int)
        self.cooldowns: dict[str, float] = defaultdict(float)

    def register_failure(self, key: str) -> None:
        self.failures[key] += 1
        if self.failures[key] >= self.max_failures:
            self.cooldowns[key] = time.time() + self.cooldown_seconds

    def register_success(self, key: str) -> None:
        self.failures[key] = 0
        self.cooldowns.pop(key, None)

    def is_blocked(self, key: str) -> bool:
        until = self.cooldowns.get(key, 0.0)
        if until and time.time() < until:
            return True
        return False


class RollingWindow:
    def __init__(self, max_items: int = 20) -> None:
        self.max_items = max_items
        self.items: deque[str] = deque(maxlen=max_items)

    def add(self, value: str) -> None:
        self.items.append(value)

    def last(self) -> str | None:
        return self.items[-1] if self.items else None
