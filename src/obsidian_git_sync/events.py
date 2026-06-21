"""The classified change-event model and the thread-safe queue producers feed.

The extension turns the three upstream detection sources into one stream of
``SyncEvent``s on an ``EventQueue``. Two kinds carry different information:

- ``MCP_WRITE`` -- a mutation came through the MCP server. Only the write-listener
  knows this, so it alone produces it; it carries the ``operation`` and ``paths``.
- ``SYNC_SWEEP`` -- "reconcile the working tree". Produced by the .md watcher and
  the periodic timer, neither of which can know a change's origin, so it carries
  only its ``trigger`` source and no specific paths.

The queue is a thin wrapper over ``queue.Queue`` -- already thread-safe for the
multi-producer (request/watcher/timer threads) single-consumer (the worker, next
change) topology here, so a custom lock+list would only re-implement it.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass

# Event kinds. String constants (not an enum) keep SyncEvent trivially hashable and
# its repr readable; the set of kinds is tiny and closed.
MCP_WRITE = "mcp_write"
SYNC_SWEEP = "sync_sweep"


@dataclass(frozen=True)
class SyncEvent:
    """A single classified vault-change event.

    Frozen (immutable + hashable) so an event is a safe value to pass between
    producer threads and the consumer. ``paths`` is a tuple, not a list, so the
    whole dataclass stays hashable and cannot be mutated after enqueue.

    For ``MCP_WRITE``: ``operation`` is one of "created"/"updated"/"moved"/"deleted"
    and ``paths`` are the vault-relative paths it touched. For ``SYNC_SWEEP``:
    ``trigger`` is the source ("watcher" or "timer"); ``operation`` is None and
    ``paths`` is empty (a sweep reconciles the whole tree, not specific paths).
    """

    kind: str
    operation: str | None = None
    paths: tuple[str, ...] = ()
    trigger: str | None = None

    @classmethod
    def mcp_write(cls, operation: str, paths) -> "SyncEvent":
        """Build an ``MCP_WRITE`` event from a write-listener ``(operation, paths)``."""
        return cls(kind=MCP_WRITE, operation=operation, paths=tuple(paths))

    @classmethod
    def sync_sweep(cls, trigger: str) -> "SyncEvent":
        """Build a ``SYNC_SWEEP`` event tagged with its trigger source."""
        return cls(kind=SYNC_SWEEP, trigger=trigger)


class EventQueue:
    """Thread-safe queue of ``SyncEvent``s: many producers, one consumer.

    A thin wrapper over ``queue.Queue`` so the public surface is exactly what this
    project needs (``put`` from producers, ``get`` for the future worker, ``drain``
    for tests) rather than the full ``Queue`` API.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[SyncEvent] = queue.Queue()

    def put(self, event: SyncEvent) -> None:
        """Enqueue an event. Safe to call from any producer thread."""
        self._queue.put(event)

    def get(self, block: bool = True, timeout: float | None = None) -> SyncEvent:
        """Dequeue one event; same blocking semantics as ``queue.Queue.get``."""
        return self._queue.get(block=block, timeout=timeout)

    def drain(self) -> list[SyncEvent]:
        """Non-blocking: return all currently-queued events, emptying the queue.

        For tests/inspection -- the real consumer (next change) blocks on ``get``.
        """
        drained: list[SyncEvent] = []
        while True:
            try:
                drained.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return drained

    def __len__(self) -> int:
        return self._queue.qsize()
