"""The single git-worker consumer thread -- the heart of the extension.

One daemon thread drains the ``EventQueue`` and performs ALL git work; no other
thread touches git, so the flock the bobsidian origin used is replaced by
structural single-thread serialisation. The loop blocks on
``events.get(timeout=debounce)``:

- an event wakes it -> it commits IMMEDIATELY (granular history) and marks that
  there are unpushed commits;
- a ``queue.Empty`` (the queue has been quiet for the debounce window) OR a
  push that is overdue past ``push_max_interval`` -> it pushes the accumulated
  commits.

Commit and push are decoupled: per-event commits keep history granular while
pushes batch and debounce. The push sequence ports the origin's invariants
exactly -- commit-local-first, ``fetch`` then ``rebase -X theirs origin/<branch>``,
``rebase --abort`` + log on failure (NEVER commit conflict markers), and an
offline-tolerant push (skip the rebase if fetch failed, still try the push).

Fail-soft everywhere except startup validation: every git call is wrapped, a
failure is logged and swallowed, the loop keeps running, and unpushed commits
retry on the next cycle. This is the upstream house rule applied to the worker.
"""

from __future__ import annotations

import logging
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone

from . import config, heartbeat, stamping
from .events import MCP_WRITE, SYNC_SWEEP, EventQueue
from .git_ops import GitOps

logger = logging.getLogger(__name__)


def _mcp_message(operation: str | None, paths: tuple[str, ...]) -> str:
    """Build an ``mcp: <op> <paths>`` commit message.

    A single path verbatim; otherwise the first three joined by ", " followed by
    ``(+N more)``. Mirrors the bobsidian origin's preview-with-truncation so the
    history reads the same.
    """
    if len(paths) == 1:
        summary = paths[0]
    else:
        preview = ", ".join(paths[:3])
        if len(paths) > 3:
            preview = f"{preview} (+{len(paths) - 3} more)"
        summary = preview
    return f"mcp: {operation} {summary}"


def _sweep_message() -> str:
    """Build a ``sync: auto <UTC-timestamp>`` message in ``YYYY-MM-DDTHH:MM:SSZ``.

    The timestamp is generated here (runtime code, not a workflow script, so
    ``datetime.now`` is fine) and matches the origin's ``date -u`` format exactly.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"sync: auto {ts}"


class GitWorker:
    """The consumer thread: drains events, commits per event, pushes batched.

    Construct with the shared ``EventQueue`` and a ``GitOps`` (tests inject one
    against a tmp repo; production builds one from ``config``). ``start()`` spawns
    the daemon thread running ``run()``; ``stop()`` signals it, joins, and does a
    best-effort final flush.
    """

    def __init__(
        self,
        events: EventQueue,
        git: GitOps,
        *,
        remote: str = "",
        branch: str = "",
        push_debounce: float = 10.0,
        push_max_interval: float = 300.0,
        heartbeat_url: str = "",
    ) -> None:
        self.events = events
        self.git = git
        # remote == "" -> commit-only mode (never push).
        self._remote = remote
        # branch == "" -> resolve the working tree's current branch lazily.
        self._branch = branch
        self._push_debounce = push_debounce
        self._push_max_interval = push_max_interval
        # heartbeat_url == "" -> no push heartbeat (the default).
        self._heartbeat_url = heartbeat_url

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Set when a commit is made and cleared on a successful push; the loop
        # pushes only when this is set, so a quiet idle queue never pushes.
        self._unpushed = False
        # Monotonic-ish wall clock of the last successful push, to enforce the
        # max-interval guard under sustained load.
        self._last_push = self._now()

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    @classmethod
    def from_config(cls, events: EventQueue, vault) -> "GitWorker":
        """Build a worker from ``VAULT_GIT_*`` config (production path).

        Call only after ``validate_gitsync()`` has accepted the config -- the
        accessors parse here without re-checking.
        """
        git = GitOps(
            vault,
            author_name=config.author_name(),
            author_email=config.author_email(),
        )
        return cls(
            events,
            git,
            remote=config.remote(),
            branch=config.branch(),
            push_debounce=config.push_debounce(),
            push_max_interval=config.push_max_interval(),
            heartbeat_url=config.heartbeat_url(),
        )

    # --- Thread lifecycle --------------------------------------------------

    def start(self) -> None:
        """Spawn the daemon worker thread. Daemon so it never blocks process exit."""
        self._thread = threading.Thread(
            target=self.run, daemon=True, name="gitsync-worker"
        )
        self._thread.start()

    def run(self) -> None:
        """The consume-commit-push loop; exits when ``stop()`` sets the flag."""
        while not self._stop.is_set():
            try:
                event = self.events.get(timeout=self._push_debounce)
            except queue.Empty:
                # Queue quiet for the debounce window -> push window opens.
                self._maybe_push()
                continue

            self._handle_event(event)
            # A busy queue never goes quiet; the max-interval guard forces a push.
            if self._push_overdue():
                self._maybe_push()

    def stop(self) -> None:
        """Signal the loop to exit, join it, then do a best-effort final flush.

        Bounded by the git timeout. Safe to call if the thread never started.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.git.timeout + 5)
        # One last attempt to flush anything pending so shutdown loses no commits.
        self._maybe_push()

    # --- Event dispatch ----------------------------------------------------

    def _handle_event(self, event) -> None:
        """Dispatch one event by kind. Fail-soft: any error is logged + swallowed."""
        try:
            if event.kind == MCP_WRITE:
                self._handle_mcp_write(event)
            elif event.kind == SYNC_SWEEP:
                self._handle_sync_sweep(event)
        except subprocess.TimeoutExpired:
            # A wedged git command: already logged in GitOps. Move on; retry next.
            pass
        except Exception:
            logger.exception("git-worker failed handling a %s event", event.kind)

    def _handle_mcp_write(self, event) -> None:
        """Stage the event's paths and commit ``mcp: <op> <paths>`` if anything staged.

        Frontmatter stamping happens HERE, before staging, so the bumped
        ``modified`` lands in the same ``mcp:`` commit. Gated by
        ``VAULT_GIT_STAMP`` and skipped for deletes (there is no file to
        stamp). event.paths are vault-RELATIVE; the stamper needs absolute paths,
        so they are resolved against the worker's vault. Stamping is fail-soft
        (``stamp_paths`` never raises) -- a stamping failure must never stop the
        commit, so the write still stages and commits, just unstamped.
        """
        if not event.paths:
            return
        if config.stamp_enabled() and event.operation != "deleted":
            try:
                stamping.stamp_paths(
                    [self.git.vault / p for p in event.paths]
                )
            except Exception:
                logger.exception("git-worker stamping failed; committing unstamped")
        self.git.add(event.paths)
        if self.git.has_staged():
            result = self.git.commit(_mcp_message(event.operation, event.paths))
            if result.ok:
                self._unpushed = True
            else:
                logger.warning("git-worker mcp commit failed (rc=%s)", result.rc)

    def _handle_sync_sweep(self, event) -> None:
        """``git add -A`` and commit ``sync: auto <ts>`` if the tree was dirty."""
        self.git.add_all()
        if self.git.has_staged():
            result = self.git.commit(_sweep_message())
            if result.ok:
                self._unpushed = True
            else:
                logger.warning("git-worker sweep commit failed (rc=%s)", result.rc)

    # --- Push policy -------------------------------------------------------

    def _push_overdue(self) -> bool:
        """True once ``push_max_interval`` has elapsed since the last push."""
        return self._now() - self._last_push >= self._push_max_interval

    def _resolve_branch(self) -> str | None:
        """The branch to push: the configured one, else the current branch."""
        if self._branch:
            return self._branch
        return self.git.current_branch()

    def _maybe_push(self) -> None:
        """Push accumulated commits with the local-wins fetch/rebase/push sequence.

        No-op when there is nothing unpushed or no remote is configured
        (commit-only mode). Fail-soft: any git failure is logged + swallowed, the
        ``_unpushed`` flag stays set, and the commits retry next cycle.
        """
        if not self._unpushed or not self._remote:
            return

        try:
            self._push_once()
        except subprocess.TimeoutExpired:
            # A wedged fetch/rebase/push: logged in GitOps. Retry next cycle.
            pass
        except Exception:
            logger.exception("git-worker push cycle failed")

    def _push_once(self) -> None:
        """One fetch -> rebase -X theirs -> push attempt; clear unpushed on success."""
        branch = self._resolve_branch()
        if branch is None:
            logger.warning("git-worker cannot resolve a branch to push; skipping")
            return

        # Fetch first. If it fails (offline), skip the rebase but still try to
        # push -- the origin script's offline-tolerant behaviour.
        if self.git.fetch(self._remote).ok:
            rebase = self.git.rebase_theirs(self._remote, branch)
            if not rebase.ok:
                # NEVER leave or commit conflict markers: abort and log.
                self.git.rebase_abort()
                logger.warning(
                    "git-worker rebase of %s/%s failed; aborted (manual "
                    "intervention may be required)",
                    self._remote,
                    branch,
                )

        push = self.git.push(self._remote, branch)
        if push.ok:
            self._unpushed = False
            self._last_push = self._now()
            # Fire the push heartbeat only after a confirmed push (never on
            # failure, and commit-only mode never reaches here) and only when a
            # URL is configured. ping() is itself fail-soft, and the whole push
            # cycle is already exception-wrapped in _maybe_push.
            if self._heartbeat_url:
                heartbeat.ping(self._heartbeat_url)
        else:
            # Logged + swallowed; commits stay unpushed and retry next cycle.
            logger.warning("git-worker push failed (rc=%s)", push.rc)
