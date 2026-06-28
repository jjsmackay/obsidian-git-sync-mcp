"""Tests for the git-worker capability (the git-worker change).

One test (or small group) per spec scenario in
``openspec/changes/git-worker/specs/git-worker/spec.md`` and per tasks.md test
item. Every test runs against a tmp ``git init`` working tree and, where a push
is involved, a bare repo as ``origin`` -- NEVER a real remote.

Determinism: where possible we drive the worker's per-event handlers directly
(``_handle_event`` / ``_maybe_push``) rather than racing its loop. The
push-batching and disabled tests that need the real thread run it with a tiny
debounce and poll the bare remote's state with a bounded wait, then always stop
and join the thread so no daemon leaks.
"""

from __future__ import annotations

import re
import subprocess
import time

import pytest

from obsidian_git_sync import config
from obsidian_git_sync.events import EventQueue, SyncEvent
from obsidian_git_sync.extension import GitSyncExtension
from obsidian_git_sync.git_ops import GitOps
from obsidian_git_sync.worker import GitWorker, _mcp_message


# --- Helpers -------------------------------------------------------------------

def _git(cwd, *args) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def _log_messages(repo) -> list[str]:
    """Commit subjects in a repo (or a ref), newest first."""
    out = _git(repo, "log", "--format=%s")
    return [line for line in out.splitlines() if line]


def _bare_log(bare, ref="refs/heads/main") -> list[str]:
    out = _git(bare, "log", "--format=%s", ref)
    return [line for line in out.splitlines() if line]


def _make_ops(vault) -> GitOps:
    """A GitOps with a committer identity so commits succeed in CI-like envs."""
    return GitOps(vault, author_name="Worker Bot", author_email="worker@example.com")


def _worker(events, vault, **kw) -> GitWorker:
    kw.setdefault("push_debounce", 0.05)
    kw.setdefault("push_max_interval", 1000)  # don't force pushes by interval in tests
    return GitWorker(events, _make_ops(vault), **kw)


def _wait_until(predicate, timeout=5.0, interval=0.02):
    """Poll ``predicate`` until true or timeout; return its final truthiness."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


# --- Commit message formatting -------------------------------------------------

def test_mcp_message_single_path():
    assert _mcp_message("updated", ("notes/a.md",)) == "mcp: updated notes/a.md"


def test_mcp_message_many_paths_summarised():
    paths = ("a.md", "b.md", "c.md", "d.md", "e.md")
    assert _mcp_message("created", paths) == "mcp: created a.md, b.md, c.md (+2 more)"


def test_mcp_message_exactly_three_no_more_suffix():
    paths = ("a.md", "b.md", "c.md")
    assert _mcp_message("updated", paths) == "mcp: updated a.md, b.md, c.md"


# --- MCP_WRITE -> provenance-tagged commits (spec: MCP writes ...) -------------

def test_mcp_write_single_path_commit(git_remote_vault):
    """A single-path MCP_WRITE with an on-disk change -> one mcp: commit."""
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("hello\n")

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.mcp_write("updated", ["a.md"]))

    assert _log_messages(vault)[0] == "mcp: updated a.md"
    assert w._unpushed is True


def test_mcp_write_many_paths_summarised(git_remote_vault):
    """More than three paths -> message lists first three + (+N more)."""
    vault, _bare = git_remote_vault
    paths = []
    for name in ("a.md", "b.md", "c.md", "d.md"):
        (vault / name).write_text(name)
        paths.append(name)

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.mcp_write("created", paths))

    assert _log_messages(vault)[0] == "mcp: created a.md, b.md, c.md (+1 more)"


def test_mcp_write_nothing_staged_no_commit(git_remote_vault):
    """An MCP_WRITE whose file has no on-disk change makes no commit."""
    vault, _bare = git_remote_vault
    before = _log_messages(vault)

    w = _worker(EventQueue(), vault)
    # "a.md" was never created/changed, so add stages nothing.
    w._handle_event(SyncEvent.mcp_write("updated", ["a.md"]))

    assert _log_messages(vault) == before
    assert w._unpushed is False


# --- SYNC_SWEEP -> sync: auto <ts> (spec: Sweeps commit out-of-band) -----------

def test_sync_sweep_dirty_commits_with_timestamp(git_remote_vault):
    """A dirty tree on sweep -> exactly one sync: auto <ts> commit, ts format asserted."""
    vault, _bare = git_remote_vault
    (vault / "attachment.png").write_bytes(b"\x89PNG fake")

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.sync_sweep("timer"))

    subject = _log_messages(vault)[0]
    assert re.match(r"^sync: auto \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", subject), subject
    assert w._unpushed is True


def test_sync_sweep_clean_is_noop(git_remote_vault):
    """A clean tree on sweep makes no commit."""
    vault, _bare = git_remote_vault
    before = _log_messages(vault)

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.sync_sweep("timer"))

    assert _log_messages(vault) == before
    assert w._unpushed is False


def test_mcp_write_then_sweep_no_duplicate(git_remote_vault):
    """An MCP write committed, then a sweep for the same unchanged file -> no dup."""
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("body\n")

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))
    after_mcp = _log_messages(vault)
    # Tree is now clean; a sweep should find nothing.
    w._handle_event(SyncEvent.sync_sweep("watcher"))

    assert _log_messages(vault) == after_mcp


# --- Push policy (spec: Commit and push are decoupled and debounced) -----------

def test_push_batches_multiple_commits_after_quiet(git_remote_vault):
    """Several events then quiet -> exactly one push delivers all commits."""
    vault, bare = git_remote_vault
    events = EventQueue()
    w = _worker(events, vault, remote="origin", branch="main")
    w.start()
    try:
        for name in ("a.md", "b.md", "c.md"):
            (vault / name).write_text(name)
            events.put(SyncEvent.mcp_write("created", [name]))

        # Wait until the bare remote has all three commits on top of "initial".
        ok = _wait_until(lambda: len(_bare_log(bare)) == 4)
        assert ok, _bare_log(bare)
    finally:
        w.stop()

    subjects = _bare_log(bare)
    assert subjects[-1] == "initial"
    assert {"mcp: created a.md", "mcp: created b.md", "mcp: created c.md"} <= set(subjects)


def test_commit_only_mode_no_push(git_remote_vault):
    """No remote configured -> commits exist locally, bare remote unchanged."""
    vault, bare = git_remote_vault
    before_remote = _bare_log(bare)

    events = EventQueue()
    w = _worker(events, vault, remote="", branch="main")  # commit-only
    w.start()
    try:
        (vault / "a.md").write_text("x")
        events.put(SyncEvent.mcp_write("created", ["a.md"]))
        # Local commit appears...
        assert _wait_until(lambda: _log_messages(vault) and _log_messages(vault)[0] == "mcp: created a.md")
        # ...give a push window the chance to (wrongly) fire, then assert it didn't.
        time.sleep(0.3)
    finally:
        w.stop()

    assert _bare_log(bare) == before_remote


# --- Local-wins sync (spec: Local-wins sync without conflict markers) ----------

def test_diverged_remote_rebased_local_wins_no_markers(git_remote_vault, tmp_path):
    """Remote has commits the local lacks -> fetch + rebase -X theirs + push, no markers."""
    vault, bare = git_remote_vault

    # Make a diverging commit directly via a second clone and push it to origin,
    # touching the SAME file the worker will also change -> a content conflict.
    other = tmp_path / "other"
    _git(tmp_path, "clone", str(bare), str(other))
    # The bare repo's HEAD may name a different default branch, so the clone lands
    # on that; check out main (tracking origin/main) explicitly.
    _git(other, "checkout", "main")
    _git(other, "config", "user.name", "Other")
    _git(other, "config", "user.email", "other@example.com")
    (other / "shared.md").write_text("remote version\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "remote: shared")
    _git(other, "push", "origin", "main")

    # Local change to the same file, then drive a single push cycle synchronously.
    (vault / "shared.md").write_text("local version\n")
    w = _worker(EventQueue(), vault, remote="origin", branch="main")
    w._handle_event(SyncEvent.mcp_write("created", ["shared.md"]))
    w._maybe_push()

    # No conflict markers anywhere in the working tree.
    markers = subprocess.run(
        ["git", "-C", str(vault), "grep", "-l", "<<<<<<<"],
        capture_output=True, text=True,
    )
    assert markers.stdout.strip() == "", markers.stdout
    # Local content won (-X theirs favours the replayed local commits).
    assert (vault / "shared.md").read_text() == "local version\n"
    # The push landed and the flag cleared.
    assert w._unpushed is False
    assert "mcp: created shared.md" in _bare_log(bare)


def test_rebase_failure_aborts_clean_and_worker_survives(git_remote_vault, monkeypatch):
    """A forced rebase failure -> --abort leaves a clean tree; the worker still runs."""
    vault, bare = git_remote_vault
    (vault / "a.md").write_text("local\n")

    w = _worker(EventQueue(), vault, remote="origin", branch="main")
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))

    # Force the rebase to "fail" so we exercise the abort path deterministically.
    from obsidian_git_sync.git_ops import GitResult
    real_abort = w.git.rebase_abort
    abort_called = {"n": 0}

    def counting_abort():
        abort_called["n"] += 1
        return real_abort()

    monkeypatch.setattr(w.git, "rebase_theirs", lambda r, b: GitResult(1, "", "boom"))
    monkeypatch.setattr(w.git, "rebase_abort", counting_abort)

    w._maybe_push()

    assert abort_called["n"] == 1
    # Tree is clean (no in-progress rebase, no conflict markers).
    assert not w.git.is_dirty()
    assert not (vault / ".git" / "rebase-merge").exists()
    assert not (vault / ".git" / "rebase-apply").exists()
    # The worker is unharmed: a subsequent normal cycle pushes fine.
    monkeypatch.undo()
    w._maybe_push()
    assert w._unpushed is False
    assert "mcp: created a.md" in _bare_log(bare)


# --- Fail-soft (spec: Worker failures never crash the server) ------------------

def test_failing_push_logged_and_later_push_succeeds(git_remote_vault, tmp_path):
    """A failing push is swallowed, the worker survives, and a later push succeeds."""
    vault, bare = git_remote_vault
    (vault / "a.md").write_text("x")

    w = _worker(EventQueue(), vault, remote="origin", branch="main")
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))

    # Break origin: point it at a non-existent path so fetch+push fail.
    _git(vault, "remote", "set-url", "origin", str(tmp_path / "does-not-exist.git"))
    w._maybe_push()  # must not raise
    assert w._unpushed is True  # commit retained for retry

    # Restore origin; the next cycle pushes the retained commit.
    _git(vault, "remote", "set-url", "origin", str(bare))
    w._maybe_push()
    assert w._unpushed is False
    assert "mcp: created a.md" in _bare_log(bare)


def test_handle_event_swallows_exceptions(git_remote_vault, monkeypatch):
    """An unexpected error inside event handling is logged + swallowed, not raised."""
    vault, _bare = git_remote_vault
    w = _worker(EventQueue(), vault)

    def boom(_paths):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(w.git, "add", boom)
    # Must not raise.
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))


# --- Frontmatter stamping in the MCP-write commit (frontmatter-stamping) -------

_MODIFIED_RE = re.compile(r"^modified: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", re.MULTILINE)


def test_mcp_write_stamped_within_commit(git_remote_vault, monkeypatch):
    """Enabled stamping -> the mcp: commit's content carries a bumped, unquoted modified."""
    monkeypatch.setattr(config, "VAULT_GIT_STAMP", "true")
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("---\ntitle: hi\n---\nbody\n")

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.mcp_write("updated", ["a.md"]))

    assert _log_messages(vault)[0] == "mcp: updated a.md"
    # Read the committed blob back from HEAD (not just the working tree).
    committed = _git(vault, "show", "HEAD:a.md")
    assert _MODIFIED_RE.search(committed), committed
    assert "modified: '" not in committed  # unquoted


def test_mcp_write_deleted_not_stamped(git_remote_vault, monkeypatch):
    """Operation 'deleted' is never stamped (there is no file to stamp)."""
    monkeypatch.setattr(config, "VAULT_GIT_STAMP", "true")
    vault, _bare = git_remote_vault
    # Commit a file, then delete it on disk and fire a deleted MCP_WRITE.
    (vault / "gone.md").write_text("---\ntitle: hi\n---\nbody\n")
    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.mcp_write("created", ["gone.md"]))

    # Spy on the stamper: a deleted op must not call it.
    called = {"n": 0}
    monkeypatch.setattr(
        "obsidian_git_sync.worker.stamping.stamp_paths",
        lambda paths: called.__setitem__("n", called["n"] + 1),
    )
    (vault / "gone.md").unlink()
    w._handle_event(SyncEvent.mcp_write("deleted", ["gone.md"]))

    assert called["n"] == 0
    # The delete was still committed.
    assert _log_messages(vault)[0] == "mcp: deleted gone.md"


def test_sweep_does_not_stamp(git_remote_vault, monkeypatch):
    """A SYNC_SWEEP never invokes stamping (device edits arrive pre-stamped)."""
    monkeypatch.setattr(config, "VAULT_GIT_STAMP", "true")
    vault, _bare = git_remote_vault
    (vault / "note.md").write_text("---\ntitle: hi\n---\nbody\n")

    called = {"n": 0}
    monkeypatch.setattr(
        "obsidian_git_sync.worker.stamping.stamp_paths",
        lambda paths: called.__setitem__("n", called["n"] + 1),
    )
    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.sync_sweep("timer"))

    assert called["n"] == 0


def test_stamping_disabled_commits_file_verbatim(git_remote_vault, monkeypatch):
    """VAULT_GIT_STAMP=false -> committed file byte-identical to what was written."""
    monkeypatch.setattr(config, "VAULT_GIT_STAMP", "false")
    vault, _bare = git_remote_vault
    written = "---\ntitle: hi\n---\nbody\n"
    (vault / "a.md").write_text(written)

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.mcp_write("updated", ["a.md"]))

    committed = _git(vault, "show", "HEAD:a.md")
    assert committed == written  # no modified added


def test_mcp_write_malformed_frontmatter_still_committed(git_remote_vault, monkeypatch):
    """Malformed frontmatter is logged, not raised; the file is committed unstamped."""
    monkeypatch.setattr(config, "VAULT_GIT_STAMP", "true")
    vault, _bare = git_remote_vault
    written = "---\na: b: c\n---\nbody\n"
    (vault / "bad.md").write_text(written)

    w = _worker(EventQueue(), vault)
    w._handle_event(SyncEvent.mcp_write("updated", ["bad.md"]))  # must not raise

    # Committed, and unstamped (the stamp failed fail-soft).
    assert _log_messages(vault)[0] == "mcp: updated bad.md"
    assert _git(vault, "show", "HEAD:bad.md") == written


# --- Disabled starts no worker (spec: Single git-worker consumer thread) -------

def test_disabled_starts_no_worker(gitsync_disabled, vault_dir):
    """Disabled extension -> no worker thread is created and no git is invoked."""
    from obsidian_vault_mcp.frontmatter_index import FrontmatterIndex

    ext = GitSyncExtension()
    ext.before_indexes_start(FrontmatterIndex())
    ext.after_indexes_start(FrontmatterIndex())

    assert ext._worker is None
    ext.shutdown()  # safe with no worker


def test_enabled_extension_starts_one_worker(gitsync_enabled, git_remote_vault, monkeypatch):
    """Enabled -> after_indexes_start starts exactly one worker thread; shutdown stops it."""
    from obsidian_vault_mcp.frontmatter_index import FrontmatterIndex

    # gitsync_enabled defaults REMOTE="" (commit-only); this vault has a real
    # origin, so allow the worker to use it and validate against it.
    monkeypatch.setattr(config, "VAULT_GIT_REMOTE", "origin")
    monkeypatch.setattr(config, "VAULT_GIT_BRANCH", "main")
    monkeypatch.setattr(config, "VAULT_GIT_PUSH_DEBOUNCE", "0.05")

    ext = GitSyncExtension()
    ext.before_indexes_start(FrontmatterIndex())
    ext.after_indexes_start(FrontmatterIndex())
    try:
        assert ext._worker is not None
        assert ext._worker._thread is not None
        assert ext._worker._thread.is_alive()
    finally:
        ext.shutdown()
        assert not ext._worker._thread.is_alive()


# --- Config validation (spec: startup fail-closed) -----------------------------

def test_validate_rejects_missing_remote_when_enabled(gitsync_enabled, git_vault_dir, monkeypatch):
    """A configured remote that does not exist fails closed when enabled."""
    monkeypatch.setattr(config, "VAULT_GIT_REMOTE", "origin")  # not added to git_vault_dir
    with pytest.raises(ValueError, match="VAULT_GIT_REMOTE"):
        config.validate_gitsync()


def test_validate_accepts_existing_remote(gitsync_enabled, git_remote_vault, monkeypatch):
    """A configured remote that exists validates."""
    monkeypatch.setattr(config, "VAULT_GIT_REMOTE", "origin")
    config.validate_gitsync()  # must not raise


def test_validate_commit_only_mode_skips_remote_check(gitsync_enabled, git_vault_dir):
    """Commit-only mode (REMOTE="") validates without any remote present."""
    # gitsync_enabled already sets REMOTE="".
    config.validate_gitsync()  # must not raise


@pytest.mark.parametrize("bad", ["0", "-1", "notanum", ""])
def test_validate_rejects_bad_push_debounce(gitsync_enabled, git_vault_dir, monkeypatch, bad):
    monkeypatch.setattr(config, "VAULT_GIT_PUSH_DEBOUNCE", bad)
    with pytest.raises(ValueError, match="VAULT_GIT_PUSH_DEBOUNCE"):
        config.validate_gitsync()


@pytest.mark.parametrize("bad", ["0", "-5", "notanum", ""])
def test_validate_rejects_bad_push_max_interval(gitsync_enabled, git_vault_dir, monkeypatch, bad):
    monkeypatch.setattr(config, "VAULT_GIT_PUSH_MAX_INTERVAL", bad)
    with pytest.raises(ValueError, match="VAULT_GIT_PUSH_MAX_INTERVAL"):
        config.validate_gitsync()


def test_validate_accepts_default_push_timing(gitsync_enabled, git_vault_dir):
    config.validate_gitsync()
    assert config.push_debounce() == 10.0
    assert config.push_max_interval() == 300.0


# --- Push credential: VAULT_GIT_TOKEN (spec: git-credential-helper) -------------

def test_token_reads_env_stripped(monkeypatch):
    """``token()`` returns the configured token with surrounding whitespace removed."""
    monkeypatch.setattr(config, "VAULT_GIT_TOKEN", "  ghp_abc123  ")
    assert config.token() == "ghp_abc123"


def test_token_empty_when_unset(monkeypatch):
    """An unset/empty ``VAULT_GIT_TOKEN`` yields the empty string (no token)."""
    monkeypatch.setattr(config, "VAULT_GIT_TOKEN", "")
    assert config.token() == ""


def _set_remote_url(vault, url, monkeypatch):
    """Point ``origin`` at ``url`` and select it as the configured remote."""
    _git(vault, "remote", "add", "origin", url)
    monkeypatch.setattr(config, "VAULT_GIT_REMOTE", "origin")
    monkeypatch.setattr(config, "VAULT_GIT_TOKEN", "")


def test_validate_rejects_https_remote_without_token(gitsync_enabled, git_vault_dir, monkeypatch):
    """A tokenless HTTPS remote with no VAULT_GIT_TOKEN fails closed at startup."""
    url = "https://github.com/owner/secret-repo.git"
    _set_remote_url(git_vault_dir, url, monkeypatch)

    with pytest.raises(ValueError, match="VAULT_GIT_TOKEN") as exc:
        config.validate_gitsync()

    # The message names the missing credential but never echoes the remote URL.
    assert "owner/secret-repo" not in str(exc.value)
    assert url not in str(exc.value)


def test_validate_accepts_https_remote_with_token(gitsync_enabled, git_vault_dir, monkeypatch):
    """A tokenless HTTPS remote validates once VAULT_GIT_TOKEN is set."""
    _set_remote_url(git_vault_dir, "https://github.com/owner/repo.git", monkeypatch)
    monkeypatch.setattr(config, "VAULT_GIT_TOKEN", "ghp_token")
    config.validate_gitsync()  # must not raise


def test_validate_ssh_remote_needs_no_token(gitsync_enabled, git_vault_dir, monkeypatch):
    """An SSH remote authenticates by key, so no token is required."""
    _set_remote_url(git_vault_dir, "git@github.com:owner/repo.git", monkeypatch)
    config.validate_gitsync()  # must not raise


def test_validate_embedded_credential_remote_needs_no_token(gitsync_enabled, git_vault_dir, monkeypatch):
    """An HTTPS URL that already embeds a credential validates without a token."""
    _set_remote_url(
        git_vault_dir, "https://x-access-token:tok@github.com/owner/repo.git", monkeypatch
    )
    config.validate_gitsync()  # must not raise


# --- Committer identity: fail closed (spec: git-committer-identity-check) -------

def _isolate_git_identity(vault, monkeypatch):
    """Reproduce a vault with no resolvable committer identity.

    Points global/system config at /dev/null and clears the ``GIT_*`` / ``EMAIL``
    env git would auto-detect from, then sets ``user.useConfigOnly`` so git
    refuses to invent a ``user@host`` identity from the gecos/hostname -- the
    behaviour a stripped container has, but which a dev host with a gecos fallback
    does not, so without it the failure path could not be exercised here.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    for var in (
        "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
        "EMAIL",
    ):
        monkeypatch.delenv(var, raising=False)
    _git(vault, "config", "user.useConfigOnly", "true")


def test_validate_accepts_env_committer_identity(gitsync_enabled, git_vault_dir, monkeypatch):
    """The configured VAULT_GIT_GIT_AUTHOR_* identity passes even with no host identity."""
    _isolate_git_identity(git_vault_dir, monkeypatch)
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_NAME", "Vault Bot")
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_EMAIL", "bot@example.com")
    config.validate_gitsync()  # must not raise


def test_validate_accepts_host_committer_identity(gitsync_enabled, git_vault_dir, monkeypatch):
    """A host-resolved identity (here local repo config) passes with no env identity set."""
    _isolate_git_identity(git_vault_dir, monkeypatch)
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_NAME", "")
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_EMAIL", "")
    _git(git_vault_dir, "config", "user.name", "Host User")
    _git(git_vault_dir, "config", "user.email", "host@example.com")
    config.validate_gitsync()  # must not raise


def test_validate_rejects_unresolvable_committer_identity(gitsync_enabled, git_vault_dir, monkeypatch):
    """Neither env nor host identity resolvable fails closed, naming the remedy."""
    _isolate_git_identity(git_vault_dir, monkeypatch)
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_NAME", "")
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_EMAIL", "")

    with pytest.raises(ValueError, match="VAULT_GIT_GIT_AUTHOR_NAME") as exc:
        config.validate_gitsync()
    assert "VAULT_GIT_GIT_AUTHOR_EMAIL" in str(exc.value)


def test_validate_skips_identity_check_when_disabled(gitsync_disabled, git_vault_dir, monkeypatch):
    """Disabled extension performs no identity check, even with no resolvable identity."""
    _isolate_git_identity(git_vault_dir, monkeypatch)
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_NAME", "")
    monkeypatch.setattr(config, "VAULT_GIT_GIT_AUTHOR_EMAIL", "")
    config.validate_gitsync()  # must not raise


# --- GitOps credential-helper wiring (spec: git-credential-helper) --------------

def _capture_git_calls(monkeypatch):
    """Record every argv GitOps hands to subprocess.run; each call succeeds (rc 0)."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("obsidian_git_sync.git_ops.subprocess.run", fake_run)
    return calls


def test_fetch_prepends_credential_helper(monkeypatch):
    """fetch clears any inherited helper then sets the env helper, before the subcommand."""
    calls = _capture_git_calls(monkeypatch)
    GitOps("/vault", credential_helper="obsidian-env").fetch("origin")
    assert calls[0] == [
        "git", "-C", "/vault",
        "-c", "credential.helper=", "-c", "credential.helper=obsidian-env",
        "fetch", "origin",
    ]


def test_push_prepends_credential_helper(monkeypatch):
    calls = _capture_git_calls(monkeypatch)
    GitOps("/vault", credential_helper="obsidian-env").push("origin", "main")
    assert calls[0] == [
        "git", "-C", "/vault",
        "-c", "credential.helper=", "-c", "credential.helper=obsidian-env",
        "push", "origin", "main",
    ]


def test_non_network_ops_omit_credential_helper(monkeypatch):
    """rebase ops never touch the remote, so they carry no credential config."""
    calls = _capture_git_calls(monkeypatch)
    ops = GitOps("/vault", credential_helper="obsidian-env")
    ops.rebase_theirs("origin", "main")
    ops.rebase_abort()
    for cmd in calls:
        assert not any("credential.helper" in part for part in cmd)


def test_no_helper_leaves_invocation_unchanged(monkeypatch):
    """Without a configured helper, fetch is exactly today's argv (no new -c args)."""
    calls = _capture_git_calls(monkeypatch)
    GitOps("/vault").fetch("origin")
    assert calls[0] == ["git", "-C", "/vault", "fetch", "origin"]


def test_from_config_sets_credential_helper_when_token(vault_dir, monkeypatch):
    """from_config wires the env helper into GitOps when a token is configured."""
    from obsidian_git_sync.credential_helper import HELPER_NAME
    from obsidian_git_sync.events import EventQueue

    monkeypatch.setattr(config, "VAULT_GIT_TOKEN", "ghp_token")
    w = GitWorker.from_config(EventQueue(), vault_dir)
    assert w.git.credential_helper == HELPER_NAME


def test_from_config_no_credential_helper_without_token(vault_dir, monkeypatch):
    """from_config leaves the helper unset when no token is configured."""
    from obsidian_git_sync.events import EventQueue

    monkeypatch.setattr(config, "VAULT_GIT_TOKEN", "")
    w = GitWorker.from_config(EventQueue(), vault_dir)
    assert w.git.credential_helper is None


# --- Push heartbeat (spec: monitoring) -----------------------------------------

_HEARTBEAT_URL = "https://monitor.example/ping/abc123"


def test_successful_push_fires_one_heartbeat(git_remote_vault, monkeypatch):
    """A successful push to the bare remote fires exactly one ping with the URL."""
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("x")

    pings = []
    monkeypatch.setattr(
        "obsidian_git_sync.worker.heartbeat.ping", lambda url: pings.append(url)
    )

    w = _worker(
        EventQueue(), vault, remote="origin", branch="main",
        heartbeat_url=_HEARTBEAT_URL,
    )
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))
    w._maybe_push()

    assert w._unpushed is False
    assert pings == [_HEARTBEAT_URL]


def test_failed_push_fires_no_heartbeat(git_remote_vault, tmp_path, monkeypatch):
    """A failed push (bad remote URL) fires no ping."""
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("x")

    pings = []
    monkeypatch.setattr(
        "obsidian_git_sync.worker.heartbeat.ping", lambda url: pings.append(url)
    )

    w = _worker(
        EventQueue(), vault, remote="origin", branch="main",
        heartbeat_url=_HEARTBEAT_URL,
    )
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))
    _git(vault, "remote", "set-url", "origin", str(tmp_path / "does-not-exist.git"))
    w._maybe_push()  # must not raise

    assert w._unpushed is True
    assert pings == []


def test_commit_only_mode_fires_no_heartbeat(git_remote_vault, monkeypatch):
    """Commit-only mode (no remote) never reaches a push, so it never pings."""
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("x")

    pings = []
    monkeypatch.setattr(
        "obsidian_git_sync.worker.heartbeat.ping", lambda url: pings.append(url)
    )

    w = _worker(EventQueue(), vault, remote="", branch="main", heartbeat_url=_HEARTBEAT_URL)
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))
    w._maybe_push()

    assert pings == []


def test_no_heartbeat_url_never_pings(git_remote_vault, monkeypatch):
    """No URL configured -> no ping even on a successful push."""
    vault, _bare = git_remote_vault
    (vault / "a.md").write_text("x")

    pings = []
    monkeypatch.setattr(
        "obsidian_git_sync.worker.heartbeat.ping", lambda url: pings.append(url)
    )

    w = _worker(EventQueue(), vault, remote="origin", branch="main")  # no heartbeat_url
    w._handle_event(SyncEvent.mcp_write("created", ["a.md"]))
    w._maybe_push()

    assert w._unpushed is False
    assert pings == []


def test_from_config_passes_heartbeat_url(gitsync_enabled, git_remote_vault, monkeypatch):
    """from_config wires config.heartbeat_url() into the worker."""
    monkeypatch.setattr(config, "VAULT_GIT_REMOTE", "origin")
    monkeypatch.setattr(config, "VAULT_GIT_HEARTBEAT_URL", _HEARTBEAT_URL)

    import obsidian_vault_mcp.config as upstream_config

    w = GitWorker.from_config(EventQueue(), upstream_config.VAULT_PATH)
    assert w._heartbeat_url == _HEARTBEAT_URL


# --- Heartbeat config validation (spec: validated fail-closed) -----------------

@pytest.mark.parametrize("bad", ["ftp://x", "not-a-url", "http://", "https://:8080/x"])
def test_validate_rejects_bad_heartbeat_url(gitsync_enabled, git_vault_dir, monkeypatch, bad):
    monkeypatch.setattr(config, "VAULT_GIT_HEARTBEAT_URL", bad)
    with pytest.raises(ValueError, match="VAULT_GIT_HEARTBEAT_URL"):
        config.validate_gitsync()


def test_validate_rejects_malformed_port_heartbeat_url(gitsync_enabled, git_vault_dir, monkeypatch):
    monkeypatch.setattr(config, "VAULT_GIT_HEARTBEAT_URL", "http://host:notaport/x")
    with pytest.raises(ValueError, match="VAULT_GIT_HEARTBEAT_URL"):
        config.validate_gitsync()


def test_validate_accepts_valid_heartbeat_url(gitsync_enabled, git_vault_dir, monkeypatch):
    monkeypatch.setattr(config, "VAULT_GIT_HEARTBEAT_URL", _HEARTBEAT_URL)
    config.validate_gitsync()  # must not raise


def test_validate_empty_heartbeat_url_is_valid(gitsync_enabled, git_vault_dir):
    """Empty heartbeat URL disables the feature and always validates."""
    config.validate_gitsync()  # default "" -- must not raise
    assert config.heartbeat_url() == ""


def test_validate_error_does_not_echo_url(gitsync_enabled, git_vault_dir, monkeypatch):
    """The validation error names the var but never echoes the (possibly secret) URL."""
    secret = "ftp://secret-host/super-secret-token"
    monkeypatch.setattr(config, "VAULT_GIT_HEARTBEAT_URL", secret)
    with pytest.raises(ValueError) as exc:
        config.validate_gitsync()
    assert "super-secret-token" not in str(exc.value)
    assert "secret-host" not in str(exc.value)
