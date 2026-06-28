"""Tests for the env-reading git credential helper.

The helper speaks git's credential-helper protocol: ``git`` invokes it as
``git-credential-obsidian-env <action>``. For ``get`` it prints the credential
sourced from ``VAULT_GIT_TOKEN``; ``store``/``erase`` are no-ops. The token value
is read only from the process environment -- never an argument, never a file.

One test per spec scenario in
``openspec/changes/vault-git-token-helper/specs/git-credential-helper/spec.md``.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from obsidian_git_sync.credential_helper import HELPER_NAME, main


def _fields(captured: str) -> dict[str, str]:
    """Parse ``key=value`` credential-protocol lines into a dict."""
    out = {}
    for line in captured.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def test_get_emits_credentials_from_env(monkeypatch, capsys):
    """``get`` with a token set prints username + the token as password."""
    monkeypatch.setenv("VAULT_GIT_TOKEN", "s3cret-token")

    rc = main(["get"])

    assert rc == 0
    fields = _fields(capsys.readouterr().out)
    assert fields["username"] == "x-access-token"
    assert fields["password"] == "s3cret-token"


def test_get_with_empty_token_emits_nothing(monkeypatch, capsys):
    """An empty ``VAULT_GIT_TOKEN`` yields no credential, exit 0 (git falls through)."""
    monkeypatch.setenv("VAULT_GIT_TOKEN", "   ")

    rc = main(["get"])

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_get_with_unset_token_emits_nothing(monkeypatch, capsys):
    """An unset ``VAULT_GIT_TOKEN`` yields no credential, exit 0."""
    monkeypatch.delenv("VAULT_GIT_TOKEN", raising=False)

    rc = main(["get"])

    assert rc == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("action", ["store", "erase"])
def test_store_and_erase_are_noops(monkeypatch, capsys, action):
    """``store``/``erase`` never cache or delete the env token; no output, exit 0."""
    monkeypatch.setenv("VAULT_GIT_TOKEN", "s3cret-token")

    rc = main([action])

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_installed_entry_point_responds(monkeypatch):
    """The console script is on PATH and responds, so a broken install fails loudly."""
    exe = shutil.which(f"git-credential-{HELPER_NAME}")
    assert exe, f"git-credential-{HELPER_NAME} is not installed on PATH"

    result = subprocess.run(
        [exe, "get"],
        input="",
        capture_output=True,
        text=True,
        env={"VAULT_GIT_TOKEN": "from-subprocess"},
    )

    assert result.returncode == 0
    assert "password=from-subprocess" in result.stdout
