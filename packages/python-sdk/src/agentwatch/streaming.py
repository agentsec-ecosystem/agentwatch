"""Bounded daemon->consumer push transport (M25 STR-1, PRD 42).

A per-subscriber bounded queue that **never blocks the append path**: publishing
offers to each subscriber's queue and drops on overflow while surfacing a visible
``degraded`` state. The store remains the source of truth — append happens first,
and a dropped/absent consumer cannot lose a stored record (design/streaming-views.md).
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Generic, TypeVar

T = TypeVar("T")

DEFAULT_QUEUE_SIZE = 1024


class Subscriber(Generic[T]):
    """One consumer's bounded inbox; ``overflowed`` is true while it is backpressured."""

    def __init__(self, queue_size: int) -> None:
        self._queue: deque[T] = deque(maxlen=queue_size)
        self._condition = threading.Condition()
        self.overflowed = False

    def offer(self, item: T) -> bool:
        """Enqueue ``item`` without blocking; return ``False`` when it is dropped."""
        with self._condition:
            if self._queue.maxlen is not None and len(self._queue) >= self._queue.maxlen:
                self.overflowed = True
                self._condition.notify_all()
                return False
            self._queue.append(item)
            self.overflowed = False
            self._condition.notify_all()
            return True

    def get(self, timeout: float | None = None) -> T | None:
        """Take the next item, waiting up to ``timeout`` seconds; ``None`` when empty."""
        with self._condition:
            if not self._queue:
                self._condition.wait(timeout)
            if not self._queue:
                return None
            item = self._queue.popleft()
            self.overflowed = False
            return item


class StreamHub(Generic[T]):
    """Fan-out hub with bounded queues and a visible degraded state."""

    def __init__(self, *, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        self._queue_size = queue_size
        self._subscribers: list[Subscriber[T]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> Subscriber[T]:
        subscriber: Subscriber[T] = Subscriber(self._queue_size)
        with self._lock:
            self._subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscriber[T]) -> None:
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def publish(self, item: T) -> bool:
        """Offer ``item`` to every subscriber; ``False`` if any queue overflowed."""
        with self._lock:
            subscribers = list(self._subscribers)
        delivered = True
        for subscriber in subscribers:
            if not subscriber.offer(item):
                delivered = False
        return delivered

    @property
    def degraded(self) -> bool:
        """Whether any active subscriber is currently backpressured."""
        with self._lock:
            return any(subscriber.overflowed for subscriber in self._subscribers)


__all__ = ["DEFAULT_QUEUE_SIZE", "StreamHub", "Subscriber"]