"""Tests for operator-declared additional extensions (VAULT_MCP_EXTENSIONS).

One test (or small group) per spec scenario in
``openspec/changes/load-additional-extensions/specs/extension-hosting/spec.md``:

- unset/empty/whitespace-only declares nothing and imports nothing
- one and several declared extensions load, once each, in declaration order
- whitespace padding and trailing/repeated commas are tolerated
- every rejection mode raises ValueError naming the offending entry (malformed,
  unimportable module, missing attribute, non-Extension target), and one bad
  entry rejects the whole list
- the entry point exits non-zero on a bad declaration, without reaching serve()
- GitSyncExtension stays first in the list handed to serve()
- an importable but undeclared Extension subclass is never loaded
"""

import pytest

from obsidian_vault_mcp.extensions import Extension
from obsidian_git_sync import config
from obsidian_git_sync.extension import GitSyncExtension


class DummyExtension(Extension):
    """A minimal declarable extension: every hook stays an upstream no-op."""


class OtherExtension(Extension):
    """A second declarable extension, to assert ordering and multiplicity."""


class NotAnExtension:
    """Importable, but not an ``Extension`` subclass -- must be rejected."""


# This module's own import path, so a spec can name the classes above without
# writing a throwaway module to disk.
_HERE = __name__


def _declare(monkeypatch, value):
    monkeypatch.setattr(config, "VAULT_MCP_EXTENSIONS", value)


@pytest.fixture
def served(monkeypatch):
    """Stub ``serve`` in the entry point and return the list it was handed.

    The list stays empty when the entry point exits before serving, so the
    fail-closed tests assert against the same object as the success ones.
    """
    from obsidian_git_sync import main as main_module

    captured = []
    monkeypatch.setattr(main_module, "serve", lambda exts: captured.extend(exts))
    return captured


# --- Unset declares nothing, and imports nothing -------------------------------

@pytest.mark.parametrize("empty", ["", "   ", "\t", "\n", ",", " , ,"])
def test_empty_declares_no_extensions(monkeypatch, empty):
    """Unset, empty, whitespace-only, and comma-only values all yield no extensions."""
    _declare(monkeypatch, empty)
    assert config.extra_extensions() == []


def test_unset_imports_nothing(monkeypatch):
    """With nothing declared, no resolution is attempted at all."""
    _declare(monkeypatch, "")

    def explode(spec):  # pragma: no cover -- proving it is never called
        raise AssertionError(f"resolution attempted for {spec!r} with nothing declared")

    monkeypatch.setattr(config, "_resolve_extension", explode)
    assert config.extra_extensions() == []


# --- Declared extensions resolve -----------------------------------------------

def test_single_declared_extension_resolves(monkeypatch):
    _declare(monkeypatch, f"{_HERE}:DummyExtension")
    assert config.extra_extensions() == [DummyExtension]


def test_several_declared_extensions_resolve_in_order(monkeypatch):
    """Declaration order is preserved, and each entry resolves once."""
    _declare(monkeypatch, f"{_HERE}:OtherExtension,{_HERE}:DummyExtension")
    assert config.extra_extensions() == [OtherExtension, DummyExtension]


def test_whitespace_and_stray_commas_tolerated(monkeypatch):
    """Padding, a trailing comma, and a repeated comma are not errors."""
    _declare(monkeypatch, f"  {_HERE}:DummyExtension , , {_HERE}:OtherExtension ,")
    assert config.extra_extensions() == [DummyExtension, OtherExtension]


def test_inner_whitespace_tolerated(monkeypatch):
    """Padding around the separator is stripped, not validated as malformed."""
    _declare(monkeypatch, f"{_HERE} : DummyExtension")
    assert config.extra_extensions() == [DummyExtension]


def test_repeated_entry_resolves_twice(monkeypatch):
    """A duplicate declaration is left visible rather than silently de-duplicated."""
    _declare(monkeypatch, f"{_HERE}:DummyExtension,{_HERE}:DummyExtension")
    assert config.extra_extensions() == [DummyExtension, DummyExtension]


# --- Every rejection mode fails closed, naming the entry -----------------------

@pytest.mark.parametrize(
    ("spec", "match"),
    [
        pytest.param("no_separator_at_all", "malformed", id="no-separator"),
        pytest.param(":DummyExtension", "malformed", id="empty-module"),
        pytest.param(f"{_HERE}:", "malformed", id="empty-attribute"),
        pytest.param("   :   ", "malformed", id="whitespace-only-halves"),
        pytest.param(
            "obsidian_git_sync.no_such_module_xyz:Thing",
            "could not be imported",
            id="unimportable-module",
        ),
        pytest.param(f"{_HERE}:NoSuchClass", "does not define", id="missing-attribute"),
        pytest.param(f"{_HERE}:NotAnExtension", "not a subclass", id="not-an-extension"),
        # A resolvable non-class (a module-level constant) is rejected too.
        pytest.param(f"{_HERE}:_HERE", "not a subclass", id="not-a-class"),
    ],
)
def test_bad_entry_rejected(monkeypatch, spec, match):
    _declare(monkeypatch, spec)
    with pytest.raises(ValueError, match=match):
        config.extra_extensions()


def test_error_names_the_offending_entry(monkeypatch):
    """The message identifies WHICH entry was rejected, not just that one was."""
    _declare(monkeypatch, f"{_HERE}:DummyExtension,{_HERE}:NoSuchClass")
    with pytest.raises(ValueError, match="NoSuchClass"):
        config.extra_extensions()


# --- The entry point composes and fails closed ---------------------------------

def test_entry_point_loads_declared_extension_after_gitsync(
    gitsync_enabled, git_vault_dir, monkeypatch, served
):
    """Declared extensions reach serve(), with GitSyncExtension first."""
    from obsidian_git_sync import main as main_module

    _declare(monkeypatch, f"{_HERE}:DummyExtension,{_HERE}:OtherExtension")
    main_module.main()  # must not exit

    assert len(served) == 3
    assert isinstance(served[0], GitSyncExtension)  # git-sync loads FIRST
    assert isinstance(served[1], DummyExtension)    # then declaration order
    assert isinstance(served[2], OtherExtension)


def test_entry_point_loads_only_gitsync_when_undeclared(
    gitsync_enabled, git_vault_dir, monkeypatch, served
):
    """An importable but undeclared Extension subclass is never loaded.

    ``DummyExtension`` above is importable throughout this module, so a single
    extension in ``served`` is the assertion that installation alone loads nothing.
    """
    from obsidian_git_sync import main as main_module

    _declare(monkeypatch, "")
    main_module.main()

    assert len(served) == 1
    assert isinstance(served[0], GitSyncExtension)


def test_entry_point_exits_nonzero_on_bad_declaration(
    gitsync_enabled, git_vault_dir, monkeypatch, served
):
    """A bad declaration refuses the boot without reaching serve().

    All-or-nothing: the list names a resolvable entry first, and nothing loads.
    """
    from obsidian_git_sync import main as main_module

    _declare(monkeypatch, f"{_HERE}:DummyExtension,{_HERE}:NoSuchClass")

    with pytest.raises(SystemExit) as exc:
        main_module.main()
    assert exc.value.code != 0
    assert served == []  # never reached serve()


def test_extensions_load_even_when_gitsync_disabled(
    gitsync_disabled, vault_dir, monkeypatch, served
):
    """A declared extension loads whether or not git sync itself is enabled."""
    from obsidian_git_sync import main as main_module

    _declare(monkeypatch, f"{_HERE}:DummyExtension")
    main_module.main()

    assert len(served) == 2
    assert isinstance(served[1], DummyExtension)
