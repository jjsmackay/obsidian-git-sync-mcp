"""Stale git lock discovery and the startup sweep that clears them.

Git takes a lock by creating ``<file>.lock`` exclusively, then renames it over
the target on success or unlinks it on failure. A killed git does neither, and
holds no kernel lock, so there is nothing to probe: the only evidence of a live
owner is a running git process. A lock left behind blocks every later ``git
add`` (rc 128) and nothing else removes it.

A git timeout gives no guarantee here. If the whole host freezes, the timer
freezes too, and it fires on resume, killing git mid-operation and leaving the
lock behind.

So: at startup, before the worker runs any git command, remove each lock that
is stale -- no git process running AND older than ``STALE_AFTER`` -- and log
every removal at warning. Never at runtime: removing a lock a live git holds
corrupts the repository, which is worse than the stall. At runtime the worker
only names the lock in its failure warning (``describe_present``).

Pure filesystem work, no git subprocess: callers pass the git directory
(``GitOps.git_dir``). The extension owns the fail-soft guard around ``sweep``.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .git_ops import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# No git command the worker runs holds a lock longer than the timeout before it
# is killed; double it for timestamp granularity and a slow kill. A lock older
# than this with no git running cannot belong to a live operation of ours.
STALE_AFTER = 2 * DEFAULT_TIMEOUT

# Where to look for running processes; tests point it at a fake tree.
PROC_ROOT = Path("/proc")


@dataclass(frozen=True)
class Lock:
    """One lock file: its absolute path, git-dir-relative name, and age in seconds."""

    path: Path
    name: str
    age: float


def find_locks(gitdir: Path) -> list[Lock]:
    """Every ``*.lock`` directly in ``gitdir`` or anywhere under ``refs/``.

    ``objects/``, ``logs/`` and ``modules/`` are deliberately not searched:
    nothing locked there blocks staging or committing, and pack and submodule
    internals are no business of ours.
    """
    now = time.time()
    candidates = [*gitdir.glob("*.lock"), *(gitdir / "refs").rglob("*.lock")]
    locks = []
    for path in sorted(candidates):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue  # Vanished between glob and stat: its owner finished.
        locks.append(Lock(path, path.relative_to(gitdir).as_posix(), now - mtime))
    return locks


def git_running() -> bool | None:
    """True if a process named ``git`` is running; None if that cannot be told.

    Inside the container this sees exactly the processes that could own a vault
    lock. Excludes the current process. Unknown must be treated as "running".
    """
    own = str(os.getpid())
    try:
        pids = [e for e in PROC_ROOT.iterdir() if e.name.isdigit() and e.name != own]
    except OSError:
        return None
    if not pids:
        return None  # A real /proc always lists at least PID 1: this is not one.
    for entry in pids:
        try:
            if (entry / "comm").read_text().strip() == "git":
                return True
        except OSError:
            continue  # Exited mid-scan, or not ours to read.
    return False


def stale_reason(lock: Lock, running: bool | None) -> str | None:
    """None if ``lock`` is safe to remove, else why it must be left in place."""
    if running is None:
        return "cannot inspect processes"
    if running:
        return "git process running"
    if lock.age < STALE_AFTER:  # Negative age (clock skew) lands here too.
        return f"younger than {STALE_AFTER:.0f}s"
    return None


def format_age(seconds: float) -> str:
    """``3d 21h 12m`` / ``12m`` / ``45s`` -- coarse, human units for a log line."""
    s = max(0, int(seconds))
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, s = divmod(s, 60)
    parts = [f"{v}{u}" for v, u in ((days, "d"), (hours, "h"), (minutes, "m")) if v]
    return " ".join(parts) if parts else f"{s}s"


def sweep(gitdir: Path) -> None:
    """Remove stale locks, one warning each; warn for each lock left in place.

    A clean repository logs nothing above debug. A failed unlink is logged and
    the sweep moves on to the next lock.
    """
    locks = find_locks(gitdir)
    if not locks:
        logger.debug("git-sync startup: no git locks present")
        return
    running = git_running()
    for lock in locks:
        reason = stale_reason(lock, running)
        age = format_age(lock.age)
        if reason is not None:
            logger.warning(
                "git-sync startup: left lock %s in place (age %s): %s",
                lock.name, age, reason,
            )
            continue
        try:
            lock.path.unlink()
        except OSError as e:
            logger.warning(
                "git-sync startup: could not remove stale lock %s (age %s): %s",
                lock.name, age, type(e).__name__,
            )
            continue
        logger.warning("git-sync startup: removed stale lock %s (age %s)", lock.name, age)


def describe_present(gitdir: Path) -> str:
    """``index.lock (age 12m), ...`` for locks present now, or "" if none.

    For the worker's runtime failure warning. Reports only; never removes.
    """
    return ", ".join(f"{lk.name} (age {format_age(lk.age)})" for lk in find_locks(gitdir))
