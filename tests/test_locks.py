"""Tests for stale git lock recovery (the recover-stale-locks change).

One test (or small group) per spec scenario in
``openspec/changes/recover-stale-locks/specs/git-worker/spec.md``. Locks are
real files in a tmp ``git init``; their age is set by back-dating the mtime.
The live-git check always runs against a fake proc root (``locks.PROC_ROOT``),
so a git process on the machine running the tests can never change an outcome.
"""

from __future__ import annotations

import re

from obsidian_git_sync import locks
from obsidian_git_sync.events import EventQueue, SyncEvent
from obsidian_git_sync.extension import GitSyncExtension

from _helpers import (
    WORKER_LOGGER, fixed_rc, git, make_lock, make_ops, make_worker, start_extension, warnings,
)

_LOCKS_LOGGER = "obsidian_git_sync.locks"
OLD = locks.STALE_AFTER + 3600


# --- Helpers -------------------------------------------------------------------

def _lock(vault, rel="index.lock", age=OLD):
    return make_lock(vault, rel, age)


def _proc(tmp_path, monkeypatch, *comms):
    """Point ``PROC_ROOT`` at a fake /proc: PID 1 plus one PID per ``comm``."""
    root = tmp_path / "proc"
    for pid, comm in enumerate(("init", *comms), start=1):
        (root / str(pid)).mkdir(parents=True)
        (root / str(pid) / "comm").write_text(f"{comm}\n")
    monkeypatch.setattr(locks, "PROC_ROOT", root)


def _gitdir(vault):
    return vault / ".git"


# --- Discovery -----------------------------------------------------------------

def test_find_locks_covers_git_dir_and_refs_not_objects(git_vault_dir):
    """index, HEAD and ref locks are found; a *.lock under objects/ is not."""
    for rel in ("index.lock", "HEAD.lock", "refs/heads/main.lock", "objects/pack/x.lock"):
        _lock(git_vault_dir, rel)

    names = [lk.name for lk in locks.find_locks(_gitdir(git_vault_dir))]

    assert names == ["HEAD.lock", "index.lock", "refs/heads/main.lock"]


def test_find_locks_reports_age(git_vault_dir):
    _lock(git_vault_dir, age=600)
    (lk,) = locks.find_locks(_gitdir(git_vault_dir))
    assert 590 < lk.age < 700


def test_git_dir_resolves_dot_git_file(git_vault_dir, tmp_path):
    """A ``.git`` FILE (worktree / separate git dir) resolves via rev-parse."""
    linked = tmp_path / "linked"
    real = tmp_path / "real.git"
    git(tmp_path, "init", "-q", f"--separate-git-dir={real}", str(linked))

    assert make_ops(linked).git_dir() == real.resolve()
    assert make_ops(git_vault_dir).git_dir() == _gitdir(git_vault_dir)


def test_git_dir_falls_back_when_not_a_repo(vault_dir):
    assert make_ops(vault_dir).git_dir() == _gitdir(vault_dir)


# --- Live git check ------------------------------------------------------------

def test_git_running_none(tmp_path, monkeypatch):
    _proc(tmp_path, monkeypatch, "python")
    assert locks.git_running() is False


def test_git_running_one(tmp_path, monkeypatch):
    _proc(tmp_path, monkeypatch, "python", "git")
    assert locks.git_running() is True


def test_git_running_unreadable_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(locks, "PROC_ROOT", tmp_path / "no-such-proc")
    assert locks.git_running() is None


def test_git_running_empty_proc_is_unknown(tmp_path, monkeypatch):
    (tmp_path / "proc").mkdir()
    monkeypatch.setattr(locks, "PROC_ROOT", tmp_path / "proc")
    assert locks.git_running() is None


# --- Staleness decision --------------------------------------------------------

def _mk(age):
    return locks.Lock(path=None, name="index.lock", age=age)


def test_stale_when_old_and_idle():
    assert locks.stale_reason(_mk(OLD), running=False) is None


def test_young_lock_not_stale():
    assert "younger" in locks.stale_reason(_mk(10), running=False)


def test_future_mtime_counts_as_young():
    assert "younger" in locks.stale_reason(_mk(-60), running=False)


def test_git_running_blocks_even_old_lock():
    assert locks.stale_reason(_mk(OLD), running=True) == "git process running"


def test_unknown_process_state_blocks():
    assert locks.stale_reason(_mk(OLD), running=None) == "cannot inspect processes"


def test_format_age():
    assert locks.format_age(3 * 86400 + 21 * 3600 + 12 * 60 + 5) == "3d 21h 12m"
    assert locks.format_age(12 * 60) == "12m"
    assert locks.format_age(45) == "45s"


# --- Startup sweep (spec: Stale repository locks are cleared at startup) -------

def test_sweep_removes_stale_locks_one_warning_each(git_vault_dir, tmp_path, monkeypatch, caplog):
    _proc(tmp_path, monkeypatch)
    idx = _lock(git_vault_dir)
    ref = _lock(git_vault_dir, "refs/heads/main.lock")

    with caplog.at_level("DEBUG", logger=_LOCKS_LOGGER):
        locks.sweep(_gitdir(git_vault_dir))

    assert not idx.exists() and not ref.exists()
    msgs = warnings(caplog, _LOCKS_LOGGER)
    assert len(msgs) == 2
    assert any(re.search(r"removed stale lock index\.lock \(age 1h", m) for m in msgs)
    assert any("removed stale lock refs/heads/main.lock" in m for m in msgs)


def test_sweep_clean_repo_logs_no_warning(git_vault_dir, caplog):
    with caplog.at_level("DEBUG", logger=_LOCKS_LOGGER):
        locks.sweep(_gitdir(git_vault_dir))
    assert warnings(caplog, _LOCKS_LOGGER) == []


def test_sweep_leaves_young_lock_with_warning(git_vault_dir, tmp_path, monkeypatch, caplog):
    _proc(tmp_path, monkeypatch)
    idx = _lock(git_vault_dir, age=30)
    with caplog.at_level("DEBUG", logger=_LOCKS_LOGGER):
        locks.sweep(_gitdir(git_vault_dir))
    assert idx.exists()
    (msg,) = warnings(caplog, _LOCKS_LOGGER)
    assert "left lock index.lock in place" in msg and "younger than" in msg


def test_sweep_leaves_locks_while_git_running(git_vault_dir, tmp_path, monkeypatch, caplog):
    _proc(tmp_path, monkeypatch, "git")
    idx = _lock(git_vault_dir)
    with caplog.at_level("DEBUG", logger=_LOCKS_LOGGER):
        locks.sweep(_gitdir(git_vault_dir))
    assert idx.exists()
    assert "git process running" in warnings(caplog, _LOCKS_LOGGER)[0]


def test_sweep_leaves_locks_when_proc_unreadable(git_vault_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(locks, "PROC_ROOT", tmp_path / "missing")
    idx = _lock(git_vault_dir)
    locks.sweep(_gitdir(git_vault_dir))
    assert idx.exists()


def test_sweep_logs_failed_unlink_and_continues(git_vault_dir, tmp_path, monkeypatch, caplog):
    """One lock can't be removed; the sweep logs it and still removes the next."""
    _proc(tmp_path, monkeypatch)
    _lock(git_vault_dir, "HEAD.lock")
    idx = _lock(git_vault_dir)
    real_unlink = type(idx).unlink

    def flaky_unlink(self, *a, **kw):
        if self.name == "HEAD.lock":
            raise PermissionError("nope")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(type(idx), "unlink", flaky_unlink)
    with caplog.at_level("DEBUG", logger=_LOCKS_LOGGER):
        locks.sweep(_gitdir(git_vault_dir))

    msgs = warnings(caplog, _LOCKS_LOGGER)
    assert any("could not remove stale lock HEAD.lock" in m for m in msgs)
    assert not idx.exists()


# --- Extension wiring ----------------------------------------------------------

def test_raising_sweep_still_starts_worker(
    gitsync_enabled, git_vault_dir, fast_worker_shutdown, monkeypatch, caplog
):
    def boom(_gitdir):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(locks, "sweep", boom)
    ext = GitSyncExtension()
    start_extension(ext)
    try:
        assert ext._worker is not None and ext._worker._thread.is_alive()
        assert any("lock sweep failed" in r.getMessage() for r in caplog.records)
    finally:
        ext.shutdown()


def test_disabled_extension_inspects_no_locks(gitsync_disabled, git_vault_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(locks, "sweep", lambda *a, **kw: calls.append(a))
    idx = _lock(git_vault_dir)

    ext = GitSyncExtension()
    start_extension(ext)
    ext.shutdown()

    assert calls == [] and idx.exists()


# --- Runtime (spec: Locks are never cleared while the worker is running) -------

def test_runtime_stage_failure_names_lock_and_leaves_it(git_remote_vault, caplog):
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("pending\n")
    idx = _lock(vault, age=720)

    with caplog.at_level("DEBUG", logger=WORKER_LOGGER):
        make_worker(EventQueue(), vault)._handle_event(SyncEvent.sync_sweep("timer"))

    (msg,) = warnings(caplog)
    assert "lock present: index.lock (age 12m)" in msg
    assert idx.exists()


def test_runtime_failure_without_lock_names_none(git_vault_dir, monkeypatch, caplog):
    w = make_worker(EventQueue(), git_vault_dir)
    monkeypatch.setattr(w.git, "add_all", fixed_rc(1))
    with caplog.at_level("DEBUG", logger=WORKER_LOGGER):
        w._handle_event(SyncEvent.sync_sweep("timer"))

    (msg,) = warnings(caplog)
    assert msg == "git-worker sweep stage failed (rc=1); worker degraded"


# --- End to end (tasks 5.1) ----------------------------------------------------

def test_end_to_end_startup_clears_locks_and_backlog_commits(
    gitsync_enabled, git_remote_vault, fast_worker_shutdown, tmp_path, monkeypatch, caplog
):
    _proc(tmp_path, monkeypatch, "python", "sh")
    vault, _bare = git_remote_vault
    before = git(vault, "rev-parse", "HEAD").strip()
    (vault / "a.md").write_text("written while wedged\n")
    (vault / "b.png").write_bytes(b"\x89PNG backlog")
    idx = _lock(vault)
    ref = _lock(vault, "refs/heads/main.lock")

    ext = GitSyncExtension()
    with caplog.at_level("DEBUG", logger=_LOCKS_LOGGER):
        start_extension(ext)
    try:
        assert not idx.exists() and not ref.exists()
        assert len(warnings(caplog, _LOCKS_LOGGER)) == 2
        assert ext._worker._thread.is_alive()

        ext._worker._handle_event(SyncEvent.sync_sweep("timer"))
        assert git(vault, "rev-parse", "HEAD").strip() != before
        changed = set(git(vault, "show", "--name-only", "--format=", "HEAD").split())
        assert {"a.md", "b.png"} <= changed
        assert ext._worker.degraded is False
    finally:
        ext.shutdown()
