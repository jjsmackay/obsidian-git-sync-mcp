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


@pytest.fixture
def gitsync_disabled(monkeypatch):
    """Force the extension's enable flag to the disabled (default) state."""
    monkeypatch.delenv("VAULT_GITSYNC_ENABLED", raising=False)
    import obsidian_git_sync.config as gs_config
    monkeypatch.setattr(gs_config, "VAULT_GITSYNC_ENABLED", "")


@pytest.fixture
def gitsync_enabled(monkeypatch):
    """Force the extension's enable flag on."""
    monkeypatch.setenv("VAULT_GITSYNC_ENABLED", "true")
    import obsidian_git_sync.config as gs_config
    monkeypatch.setattr(gs_config, "VAULT_GITSYNC_ENABLED", "true")
