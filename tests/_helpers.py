"""Plain helpers shared by the worker and lock tests (fixtures live in conftest)."""

from __future__ import annotations

import logging
import os
import subprocess
import time

from obsidian_git_sync.git_ops import GitOps, GitResult
from obsidian_git_sync.worker import GitWorker

WORKER_LOGGER = "obsidian_git_sync.worker"


def git(cwd, *args) -> str:
    """Run a git command in ``cwd`` and return stdout; raises on failure."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def make_ops(vault) -> GitOps:
    """A GitOps with a committer identity so commits succeed in CI-like envs."""
    return GitOps(vault, author_name="Worker Bot", author_email="worker@example.com")


def make_worker(events, vault, **kw) -> GitWorker:
    kw.setdefault("push_debounce", 0.05)
    kw.setdefault("push_max_interval", 1000)  # don't force pushes by interval in tests
    return GitWorker(events, make_ops(vault), **kw)


def start_extension(ext) -> None:
    """Drive the two lifecycle hooks the host calls at boot."""
    from obsidian_vault_mcp.frontmatter_index import FrontmatterIndex

    ext.before_indexes_start(FrontmatterIndex())
    ext.after_indexes_start(FrontmatterIndex())


def make_lock(vault, rel="index.lock", age=0.0):
    """Create ``.git/<rel>`` back-dated by ``age`` seconds; return its path.

    An orphaned ``index.lock`` is the real incident's trigger: ``git add`` -> rc 128.
    """
    path = vault / ".git" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    if age:
        t = time.time() - age
        os.utime(path, (t, t))
    return path


def records(caplog, level, logger=WORKER_LOGGER):
    return [r for r in caplog.records if r.name == logger and r.levelno == level]


def warnings(caplog, logger=WORKER_LOGGER) -> list[str]:
    """Warning messages ``logger`` emitted, in order."""
    return [r.getMessage() for r in records(caplog, logging.WARNING, logger)]


def fixed_rc(rc):
    """A stand-in git op that always returns ``rc``."""
    return lambda *a, **kw: GitResult(rc, "", "boom")
