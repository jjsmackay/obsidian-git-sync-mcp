"""Tests for the change-detection capability (the change-trigger change).

One test (or small group) per spec scenario in
``openspec/changes/change-trigger/specs/change-detection/spec.md``:

- a write-listener notification becomes an MCP_WRITE event
- a watcher notification becomes a SYNC_SWEEP(watcher) event
- the timer enqueues SYNC_SWEEP(timer) events on its interval
- shutdown stops the timer (no further events)
- producers on different threads enqueue safely (queue thread-safety)
- disabled wires nothing (no write/change listener, no timer)
- validate_gitsync() rejects a non-positive sweep interval when enabled
"""

import queue
import threading

import pytest

from obsidian_vault_mcp import write_events
from obsidian_vault_mcp.frontmatter_index import FrontmatterIndex

from obsidian_git_sync import config
from obsidian_git_sync.events import MCP_WRITE, SYNC_SWEEP, EventQueue, SyncEvent
from obsidian_git_sync.extension import GitSyncExtension


# --- Event model & queue -------------------------------------------------------

def test_syncevent_is_frozen_and_hashable():
    """SyncEvent is an immutable value (frozen) -- safe to pass between threads."""
    ev = SyncEvent.mcp_write("created", ["a.md", "b.md"])
    assert ev.kind == MCP_WRITE
    assert ev.operation == "created"
    assert ev.paths == ("a.md", "b.md")  # list coerced to tuple
    assert hash(ev) == hash(SyncEvent.mcp_write("created", ["a.md", "b.md"]))
    with pytest.raises(Exception):
        ev.operation = "updated"  # frozen


def test_eventqueue_put_get_drain():
    """Basic queue surface: put, get, and a non-blocking drain for tests."""
    q = EventQueue()
    q.put(SyncEvent.sync_sweep("timer"))
    q.put(SyncEvent.sync_sweep("watcher"))
    assert q.get(timeout=1).trigger == "timer"
    drained = q.drain()
    assert [e.trigger for e in drained] == ["watcher"]
    assert q.drain() == []  # now empty


# --- MCP_WRITE producer --------------------------------------------------------

def test_write_listener_notification_becomes_mcp_write(gitsync_enabled, git_vault_dir):
    """Driving fire_write after wiring enqueues an MCP_WRITE with op + paths."""
    ext = GitSyncExtension()
    ext.before_indexes_start(FrontmatterIndex())

    write_events.fire_write("moved", ["old.md", "new.md"])

    events = ext.events.drain()
    assert len(events) == 1
    ev = events[0]
    assert ev.kind == MCP_WRITE
    assert ev.operation == "moved"
    assert ev.paths == ("old.md", "new.md")


# --- SYNC_SWEEP (watcher) producer ---------------------------------------------

def test_change_listener_notification_becomes_sync_sweep(gitsync_enabled, git_vault_dir):
    """The registered change-listener, invoked, enqueues SYNC_SWEEP(trigger=watcher)."""
    idx = FrontmatterIndex()
    ext = GitSyncExtension()
    ext.before_indexes_start(idx)

    # The wiring appended exactly one change-listener to this fresh index.
    assert len(idx._change_listeners) == 1
    # Invoke it as the index would (abs_path, exists).
    idx._change_listeners[0]("/vault/some.md", True)

    events = ext.events.drain()
    assert len(events) == 1
    assert events[0].kind == SYNC_SWEEP
    assert events[0].trigger == "watcher"


# --- SYNC_SWEEP (timer) producer -----------------------------------------------

def test_timer_enqueues_sync_sweep_timer(gitsync_enabled, git_vault_dir, monkeypatch):
    """The daemon timer enqueues SYNC_SWEEP(trigger=timer) on its interval, then stops."""
    # validate_gitsync() requires an integer interval; the timer just needs a small
    # float. Patch the accessor so before_indexes_start still validates the default.
    monkeypatch.setattr(config, "sweep_interval", lambda: 0.05)
    ext = GitSyncExtension()
    ext.before_indexes_start(FrontmatterIndex())
    ext.after_indexes_start(FrontmatterIndex())
    try:
        # Wait for the first sweep rather than sleeping a fixed time (less flaky).
        ev = ext.events.get(timeout=2)
        assert ev.kind == SYNC_SWEEP
        assert ev.trigger == "timer"
    finally:
        ext.shutdown()
        if ext._timer_thread is not None:
            ext._timer_thread.join(timeout=2)
            assert not ext._timer_thread.is_alive()


def test_shutdown_stops_the_timer(gitsync_enabled, git_vault_dir, monkeypatch):
    """After shutdown the timer thread exits and enqueues no further events."""
    monkeypatch.setattr(config, "sweep_interval", lambda: 0.05)
    ext = GitSyncExtension()
    ext.before_indexes_start(FrontmatterIndex())
    ext.after_indexes_start(FrontmatterIndex())

    ext.events.get(timeout=2)  # let at least one fire
    ext.shutdown()
    ext._timer_thread.join(timeout=2)
    assert not ext._timer_thread.is_alive()

    ext.events.drain()  # clear anything queued up to the stop
    # No new event should appear after the thread has exited.
    with pytest.raises(queue.Empty):
        ext.events.get(timeout=0.3)


def test_shutdown_safe_when_timer_never_started(gitsync_disabled, vault_dir):
    """shutdown must be safe even if after_indexes_start never ran (disabled)."""
    ext = GitSyncExtension()
    ext.shutdown()  # must not raise
    assert ext._timer_thread is None


# --- Queue thread-safety -------------------------------------------------------

def test_concurrent_enqueue_loses_nothing():
    """Many producer threads enqueue concurrently; every event is retrievable."""
    q = EventQueue()
    n_threads, per_thread = 8, 500

    def producer():
        for _ in range(per_thread):
            q.put(SyncEvent.sync_sweep("timer"))

    threads = [threading.Thread(target=producer) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(q.drain()) == n_threads * per_thread


# --- Disabled wires nothing ----------------------------------------------------

def test_disabled_wires_no_producers(gitsync_disabled, vault_dir):
    """Disabled: no write listener, no change listener on the index, no timer."""
    idx = FrontmatterIndex()
    ext = GitSyncExtension()
    ext.before_indexes_start(idx)
    ext.after_indexes_start(idx)

    assert write_events._write_listeners == []  # nothing registered upstream
    assert idx._change_listeners == []          # nothing attached to the index
    assert ext._timer_thread is None            # no timer started
    assert ext.events.drain() == []             # and nothing enqueued


# --- Config validation ---------------------------------------------------------

@pytest.mark.parametrize("bad", ["0", "-1", "notanint", ""])
def test_validate_rejects_bad_sweep_interval_when_enabled(
    gitsync_enabled, git_vault_dir, monkeypatch, bad
):
    """A non-positive / non-integer sweep interval fails closed when enabled."""
    monkeypatch.setattr(config, "VAULT_GIT_SWEEP_INTERVAL", bad)
    with pytest.raises(ValueError, match="VAULT_GIT_SWEEP_INTERVAL"):
        config.validate_gitsync()


def test_validate_accepts_default_sweep_interval(gitsync_enabled, git_vault_dir):
    """The default interval validates and sweep_interval() parses it."""
    config.validate_gitsync()  # must not raise
    assert config.sweep_interval() == 60
