"""The ``GitSyncExtension`` that loads into the upstream MCP server.

It wires the three upstream change-detection sources into one ``EventQueue``:

- the MCP write-listener (``register_write_listener``) -> ``MCP_WRITE`` events,
- the .md change-listener (``FrontmatterIndex.add_change_listener``) and
- a periodic sweep timer we own -> ``SYNC_SWEEP`` events.

All wiring is gated behind the enable flag: disabled, the extension attaches
nothing and starts no thread. No consumer/git work happens here -- the worker that
drains the queue is the next change. Listeners are attached in
``before_indexes_start`` (before the index watches, so no change slips through);
the timer starts in ``after_indexes_start`` and stops in ``shutdown``.
"""

import logging
import threading

from obsidian_vault_mcp import extensions

from . import config
from .events import EventQueue, SyncEvent

logger = logging.getLogger(__name__)


class GitSyncExtension(extensions.Extension):
    """In-process git-sync extension for the obsidian-web-mcp server.

    Loaded via ``serve([GitSyncExtension()])``. Reads its enable flag at construction
    so the disabled-vs-enabled decision is fixed for the process lifetime. When
    enabled it produces classified change events onto ``self.events``; when disabled
    it is inert beyond logging that it loaded.
    """

    def __init__(self) -> None:
        # Snapshot the enable flag once; the rest of config is read only when enabled.
        self._enabled = config.is_enabled()
        # The single event stream producers feed and the future worker will drain.
        # Exposed so the worker change and tests can reach it.
        self.events = EventQueue()
        # Stop flag + handle for the daemon sweep timer (created in after_indexes_start).
        self._timer_stop = threading.Event()
        self._timer_thread: threading.Thread | None = None

    def before_indexes_start(self, frontmatter_index) -> None:
        """Validate config (fail-closed backstop), then attach the two listeners.

        A raise here propagates out of ``serve()`` and exits the process non-zero,
        so this is the backstop to the primary check in the console entry point.
        Listeners are attached HERE -- before the index starts watching -- so no
        change is missed between build and attach. Disabled: log and return.
        """
        if not self._enabled:
            logger.info("git-sync extension loaded but DISABLED (VAULT_GITSYNC_ENABLED not truthy)")
            return

        config.validate_gitsync()

        # The MCP write stream: the only source that knows a change came through MCP.
        # Maps each (operation, paths) notification to an MCP_WRITE event.
        from obsidian_vault_mcp.write_events import register_write_listener

        register_write_listener(
            lambda operation, paths: self.events.put(
                SyncEvent.mcp_write(operation, paths)
            )
        )

        # The .md watcher: sees on-disk changes regardless of origin but is blind to
        # attachments/canvas. It cannot know provenance, so it emits a SYNC_SWEEP.
        frontmatter_index.add_change_listener(
            lambda abs_path, exists: self.events.put(
                SyncEvent.sync_sweep(trigger="watcher")
            )
        )

        logger.info("git-sync extension ENABLED")

    def after_indexes_start(self, frontmatter_index) -> None:
        """Start the daemon sweep timer (enabled only).

        The timer is load-bearing: ``add_change_listener`` is .md-only, so the
        periodic full-tree sweep is the only thing that catches attachments and
        canvas files. Started after the index is built and watching.
        """
        if not self._enabled:
            return

        interval = config.sweep_interval()
        self._timer_thread = threading.Thread(
            target=self._sweep_loop, args=(interval,), daemon=True, name="gitsync-sweep"
        )
        self._timer_thread.start()

    def _sweep_loop(self, interval: float) -> None:
        """Enqueue a timer SYNC_SWEEP every ``interval`` seconds until stopped.

        ``stop.wait(interval)`` returns True the moment the stop flag is set, so
        shutdown is prompt rather than waiting out a full interval.
        """
        while not self._timer_stop.wait(interval):
            self.events.put(SyncEvent.sync_sweep(trigger="timer"))

    def shutdown(self) -> None:
        """Stop the sweep timer so it exits and enqueues nothing further.

        Registered via ``atexit`` (LIFO, before ``frontmatter_index.stop()``). Safe
        to call even if the timer never started (disabled) -- setting the event is a
        no-op then.
        """
        self._timer_stop.set()

    # register_tools, register_routes stay no-ops this change. In particular
    # register_routes adds nothing: /health is upstream-reserved and build_app()
    # rejects any extension route on an auth-exempt path.
