"""Tests for the git-sync extension scaffold.

One test (or small group) per spec scenario in
``openspec/changes/scaffold-extension/specs/git-sync-extension/spec.md``:

- disabled-by-default is a bootable no-op (build_app behaves like the stock app)
- explicitly disabled registers nothing / does no work
- enabled + valid config passes validate_gitsync() and the extension loads
- enabled + invalid config raises ValueError naming the problem, and the entry
  point exits non-zero
- the extension adds no route colliding with an auth-exempt path
"""

import pytest

from obsidian_vault_mcp import server
from obsidian_git_sync import config
from obsidian_git_sync.extension import GitSyncExtension


# --- Disabled by default: bootable no-op ---------------------------------------

def test_disabled_by_default_registers_nothing(gitsync_disabled, vault_dir):
    """No VAULT_GITSYNC_* set: extension is off and adds no tools/routes."""
    ext = GitSyncExtension()
    assert ext._enabled is False

    # register_routes is a no-op -> build_app produces the same route set as stock.
    stock_paths = {getattr(r, "path", None) for r in server.build_app([]).routes}
    ext_paths = {getattr(r, "path", None) for r in server.build_app([ext]).routes}
    assert ext_paths == stock_paths


def test_disabled_build_app_does_not_raise(gitsync_disabled, vault_dir):
    """The whole app composition with our disabled extension must build cleanly."""
    app = server.build_app([GitSyncExtension()])
    assert app is not None


def test_disabled_before_indexes_start_is_noop(gitsync_disabled, vault_dir):
    """Disabled: the lifecycle hook does no work and does not raise."""
    GitSyncExtension().before_indexes_start(object())  # must not raise


def test_disabled_validate_is_noop_even_without_git(gitsync_disabled, vault_dir):
    """validate_gitsync() must be a no-op when disabled, even if VAULT_PATH is no git repo."""
    config.validate_gitsync()  # vault_dir is not git-init'd; must not raise


# --- Explicitly disabled -------------------------------------------------------

@pytest.mark.parametrize("falsey", ["", "0", "false", "no", "off", "FALSE", "garbage"])
def test_explicitly_disabled_registers_nothing(monkeypatch, vault_dir, falsey):
    """A false (or unrecognised) enabling value disables the extension and its work."""
    monkeypatch.setattr(config, "VAULT_GITSYNC_ENABLED", falsey)
    ext = GitSyncExtension()
    assert ext._enabled is False
    ext.before_indexes_start(object())  # no work, no raise
    # No extra routes vs the stock app.
    stock_paths = {getattr(r, "path", None) for r in server.build_app([]).routes}
    ext_paths = {getattr(r, "path", None) for r in server.build_app([ext]).routes}
    assert ext_paths == stock_paths


# --- Enabled + valid config ----------------------------------------------------

def test_enabled_valid_config_passes(gitsync_enabled, git_vault_dir):
    """Enabled with a git working tree at VAULT_PATH: validation passes."""
    config.validate_gitsync()  # must not raise


def test_enabled_valid_extension_loads(gitsync_enabled, git_vault_dir):
    """Enabled + valid: the extension's startup hook runs without raising."""
    from obsidian_vault_mcp.frontmatter_index import FrontmatterIndex

    ext = GitSyncExtension()
    assert ext._enabled is True
    # Enabled now attaches a change-listener, so pass a real index, not object().
    ext.before_indexes_start(FrontmatterIndex())  # runs validate_gitsync() backstop, no raise


# --- Enabled + invalid config: fail closed -------------------------------------

def test_enabled_invalid_config_raises_naming_problem(gitsync_enabled, vault_dir):
    """Enabled but VAULT_PATH is not a git repo: ValueError naming VAULT_PATH."""
    with pytest.raises(ValueError, match="VAULT_PATH"):
        config.validate_gitsync()


def test_enabled_missing_vault_path_raises(gitsync_enabled, monkeypatch, tmp_path):
    """Enabled but VAULT_PATH does not exist: ValueError naming VAULT_PATH."""
    import obsidian_vault_mcp.config as upstream_config
    monkeypatch.setattr(upstream_config, "VAULT_PATH", tmp_path / "nope")
    with pytest.raises(ValueError, match="VAULT_PATH"):
        config.validate_gitsync()


def test_before_indexes_start_propagates_on_invalid(gitsync_enabled, vault_dir):
    """The fail-closed backstop: an invalid config raises out of the hook."""
    with pytest.raises(ValueError, match="VAULT_PATH"):
        GitSyncExtension().before_indexes_start(object())


def test_entry_point_exits_nonzero_on_invalid(gitsync_enabled, vault_dir, monkeypatch):
    """The console entry point exits non-zero on bad config without starting serve()."""
    from obsidian_git_sync import main as main_module

    called = {"serve": False}
    monkeypatch.setattr(main_module, "serve", lambda *a, **k: called.__setitem__("serve", True))

    with pytest.raises(SystemExit) as exc:
        main_module.main()
    assert exc.value.code != 0
    assert called["serve"] is False  # never reached serve()


def test_entry_point_runs_serve_when_valid(gitsync_enabled, git_vault_dir, monkeypatch):
    """Valid config: the entry point passes validation and calls serve([ext])."""
    from obsidian_git_sync import main as main_module

    captured = {}
    monkeypatch.setattr(main_module, "serve", lambda exts: captured.setdefault("exts", list(exts)))

    main_module.main()  # must not exit
    assert len(captured["exts"]) == 1
    assert isinstance(captured["exts"][0], GitSyncExtension)


# --- No collision with an auth-exempt path -------------------------------------

def test_extension_adds_no_exempt_route(gitsync_enabled, git_vault_dir):
    """register_routes is a no-op -> build_app never trips the exempt-path guard."""
    app = server.build_app([GitSyncExtension()])  # must not raise
    assert app is not None
