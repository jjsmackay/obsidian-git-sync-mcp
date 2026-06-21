"""Test fixtures for the git-sync extension.

Mirrors the upstream ``tests/conftest.py``: the upstream config reads ``VAULT_PATH``
at import, so tests set the env var AND patch the already-imported module attribute
to point at a temp vault. Our ``config.is_enabled()`` / ``validate_gitsync()`` read
``VAULT_GITSYNC_ENABLED`` and ``VAULT_PATH`` live, so monkeypatching covers both.
"""

from pathlib import Path

import pytest


@pytest.fixture
def vault_dir(tmp_path, monkeypatch):
    """A temp vault directory wired into the upstream config (NOT a git repo)."""
    vault = tmp_path / "test-vault"
    vault.mkdir()
    (vault / "test-note.md").write_text("---\nstatus: active\n---\n\nbody\n")

    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setenv("VAULT_MCP_TOKEN", "test-token-12345")

    import obsidian_vault_mcp.config as upstream_config
    monkeypatch.setattr(upstream_config, "VAULT_PATH", Path(str(vault)))

    yield vault


@pytest.fixture
def git_vault_dir(vault_dir):
    """The temp vault, ``git init``'d so it is a valid git working tree."""
    import subprocess

    subprocess.run(
        ["git", "init"], cwd=vault_dir, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    yield vault_dir


def _git(cwd, *args):
    """Run a git command in ``cwd``, raising on failure (test setup must succeed)."""
    import subprocess

    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def git_remote_vault(vault_dir, tmp_path):
    """A git working tree at VAULT_PATH with a bare ``origin`` it can push to.

    Returns ``(vault, bare)``. The vault has a committer identity (so commits work
    in CI-like envs), an initial commit, a bare repo wired as ``origin``, and an
    initial push so ``origin/<branch>`` exists for the worker to rebase onto.
    """
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(bare))

    _git(vault_dir, "init")
    _git(vault_dir, "config", "user.name", "Test Committer")
    _git(vault_dir, "config", "user.email", "test@example.com")
    # Deterministic branch name regardless of the host's init.defaultBranch.
    _git(vault_dir, "checkout", "-B", "main")
    _git(vault_dir, "add", "-A")
    _git(vault_dir, "commit", "-m", "initial")
    _git(vault_dir, "remote", "add", "origin", str(bare))
    _git(vault_dir, "push", "-u", "origin", "main")

    yield vault_dir, bare


@pytest.fixture
def gitsync_disabled(monkeypatch):
    """Force the extension's enable flag to the disabled (default) state."""
    monkeypatch.delenv("VAULT_GITSYNC_ENABLED", raising=False)
    import obsidian_git_sync.config as gs_config
    monkeypatch.setattr(gs_config, "VAULT_GITSYNC_ENABLED", "")


@pytest.fixture
def gitsync_enabled(monkeypatch):
    """Force the extension's enable flag on, in commit-only mode (no remote).

    Defaults REMOTE to "" so a bare ``git_vault_dir`` (which has no ``origin``)
    validates -- tests that exercise pushing wire up a remote and override
    ``VAULT_GITSYNC_REMOTE`` back to "origin" themselves (see ``git_remote_vault``).
    """
    monkeypatch.setenv("VAULT_GITSYNC_ENABLED", "true")
    import obsidian_git_sync.config as gs_config
    monkeypatch.setattr(gs_config, "VAULT_GITSYNC_ENABLED", "true")
    monkeypatch.setattr(gs_config, "VAULT_GITSYNC_REMOTE", "")


@pytest.fixture(autouse=True)
def reset_write_listeners():
    """Reset the upstream write-listener module-global between tests.

    ``write_events._write_listeners`` is a process-global list: each enabled
    extension appends to it, so without a reset registrations leak across tests
    and one test's listener fires during another's writes.
    """
    import obsidian_vault_mcp.write_events as write_events
    saved = list(write_events._write_listeners)
    write_events._write_listeners.clear()
    yield
    write_events._write_listeners[:] = saved
