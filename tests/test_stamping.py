"""Tests for the frontmatter-stamping capability.

One test (or small group) per spec scenario in
``openspec/changes/frontmatter-stamping/specs/frontmatter-stamping/spec.md`` and
per tasks.md test item. The load-bearing assertions are: the on-disk timestamp
is UNQUOTED ``YYYY-MM-DDTHH:MM:SSZ`` (the Linter form), existing formatting is
preserved, and the mtime-vs-``modified`` gate makes stamping idempotent.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from obsidian_git_sync import config, stamping

# An unquoted ``modified:`` line in the Linter form, anchored to a line so a
# quoted ('...') variant does NOT match -- the whole point of the quote-strip.
UNQUOTED_MODIFIED = re.compile(
    r"^modified: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", re.MULTILINE
)
UNQUOTED_CREATED = re.compile(
    r"^created: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", re.MULTILINE
)


def _epoch(ts: str) -> int:
    """Parse a Linter timestamp back to a whole-second UTC epoch."""
    return int(
        datetime.strptime(ts, stamping.TS_FORMAT)
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


# --- Requirement: Frontmatter timestamp upsert --------------------------------

def test_existing_created_preserved_modified_bumped(tmp_path):
    """Scenario: New modified, preserved created."""
    p = tmp_path / "note.md"
    p.write_text("---\ncreated: 2020-01-01T00:00:00Z\n---\n\nbody\n")

    assert stamping.stamp(p) is True

    text = p.read_text()
    assert "created: 2020-01-01T00:00:00Z" in text  # unchanged
    assert UNQUOTED_MODIFIED.search(text), text  # unquoted, bumped
    # The bumped modified is not the old created value.
    assert "modified: 2020-01-01T00:00:00Z" not in text


def test_created_added_when_missing(tmp_path):
    """Scenario: Created added when missing."""
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: hello\n---\n\nbody\n")

    assert stamping.stamp(p) is True

    text = p.read_text()
    assert UNQUOTED_CREATED.search(text), text
    assert UNQUOTED_MODIFIED.search(text), text


def test_modified_is_unquoted_not_single_quoted(tmp_path):
    """The on-disk line must be ``modified: ...Z`` -- never ``modified: '...Z'``."""
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: hi\n---\nbody\n")
    stamping.stamp(p)

    text = p.read_text()
    assert "modified: '" not in text
    assert "created: '" not in text
    assert UNQUOTED_MODIFIED.search(text), text


def test_no_frontmatter_block_gets_one_injected(tmp_path):
    """A .md with no frontmatter gets a block added (faithful to the origin)."""
    p = tmp_path / "note.md"
    p.write_text("just body, no frontmatter\n")

    assert stamping.stamp(p) is True

    text = p.read_text()
    assert text.startswith("---\n")
    assert UNQUOTED_CREATED.search(text)
    assert UNQUOTED_MODIFIED.search(text)
    assert "just body, no frontmatter\n" in text


def test_formatting_quotes_and_comments_preserved(tmp_path):
    """Scenario coverage (tasks 4.2): comments + a quoted field round-trip intact."""
    p = tmp_path / "note.md"
    p.write_text(
        "---\n"
        "# a leading comment\n"
        'title: "quoted title"\n'
        "tags:\n"
        "  - alpha\n"
        "  - beta\n"
        "created: 2021-06-01T12:00:00Z\n"
        "---\n"
        "\n"
        "body text\n"
    )

    stamping.stamp(p)

    text = p.read_text()
    assert "# a leading comment" in text  # comment preserved
    assert 'title: "quoted title"' in text  # double-quote style preserved
    # List items round-trip with their order preserved (ruamel's default
    # block-sequence indent emits them flush under the key).
    assert text.index("- alpha") < text.index("- beta")
    assert "created: 2021-06-01T12:00:00Z" in text  # untouched, unquoted
    assert UNQUOTED_MODIFIED.search(text), text
    assert "body text\n" in text


# --- Requirement: skip non-.md and missing ------------------------------------

def test_non_markdown_path_skipped(tmp_path):
    """Scenario: Non-markdown skipped."""
    p = tmp_path / "image.png"
    original = b"\x89PNG fake bytes"
    p.write_bytes(original)

    assert stamping.stamp(p) is False
    assert p.read_bytes() == original


def test_missing_path_skipped(tmp_path):
    """Scenario: missing path skipped -- no write, no raise."""
    p = tmp_path / "does-not-exist.md"
    assert stamping.stamp(p) is False
    assert not p.exists()


# --- Requirement: mtime-versus-modified gate ----------------------------------

def test_already_current_file_not_restamped(tmp_path):
    """Scenario: Already-current file is not re-stamped (idempotent)."""
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: hi\n---\nbody\n")

    assert stamping.stamp(p) is True
    after_first = p.read_bytes()

    # Pin mtime to exactly the stamped ``modified`` second so floor(mtime) ==
    # modified -- the gate must then skip. (Just-written mtime is ~now which can
    # be a fraction past the stamped whole second, so we must set it explicitly.)
    ts = UNQUOTED_MODIFIED.search(p.read_text()).group(0).split(": ", 1)[1]
    t = _epoch(ts)
    os.utime(p, (t, t))

    assert stamping.stamp(p) is False
    assert p.read_bytes() == after_first  # byte-identical


def test_stale_modified_is_restamped(tmp_path):
    """Scenario: Stale modified is stamped (floored mtime newer than modified)."""
    p = tmp_path / "note.md"
    p.write_text("---\nmodified: 2000-01-01T00:00:00Z\n---\nbody\n")
    # mtime is ~now, far newer than the year-2000 modified -> gate opens.

    assert stamping.stamp(p) is True
    text = p.read_text()
    assert "modified: 2000-01-01T00:00:00Z" not in text
    assert UNQUOTED_MODIFIED.search(text), text


def test_absent_modified_is_stamped(tmp_path):
    """Scenario: absent modified is stamped."""
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: hi\n---\nbody\n")
    assert stamping.stamp(p) is True
    assert UNQUOTED_MODIFIED.search(p.read_text())


def test_unparseable_modified_is_stamped(tmp_path):
    """A non-Linter ``modified`` value cannot gate -> file is stamped."""
    p = tmp_path / "note.md"
    p.write_text("---\nmodified: not-a-timestamp\n---\nbody\n")
    assert stamping.stamp(p) is True
    assert UNQUOTED_MODIFIED.search(p.read_text())


# --- Fail-soft: malformed frontmatter, stamp_paths ----------------------------

def test_malformed_frontmatter_logged_no_raise(tmp_path, caplog):
    """A malformed frontmatter block is logged and not raised; file untouched.

    ``a: b: c`` makes ruamel's scanner raise -- exactly the case the worker must
    survive: stamp() catches, logs, returns False, and the file is left as-is to
    be committed unstamped.
    """
    p = tmp_path / "bad.md"
    original = "---\na: b: c\n---\nbody\n"
    p.write_text(original)

    result = stamping.stamp(p)
    assert result is False
    assert p.read_text() == original


def test_stamp_paths_never_raises_and_stamps_each(tmp_path):
    """stamp_paths stamps each path and swallows per-file errors."""
    good = tmp_path / "good.md"
    good.write_text("---\ntitle: hi\n---\nbody\n")
    bad = tmp_path / "bad.md"
    bad.write_text("---\na: b: c\n---\nbody\n")
    missing = tmp_path / "missing.md"

    # Must not raise despite the malformed and missing entries.
    stamping.stamp_paths([good, bad, missing])

    assert UNQUOTED_MODIFIED.search(good.read_text())


def test_now_utc_format():
    """now_utc emits the Linter format."""
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", stamping.now_utc())


# --- Config: stamp_enabled defaults ON ----------------------------------------

def test_stamp_enabled_defaults_on(monkeypatch):
    """Unset (the default) enables stamping -- the project's reason to exist."""
    monkeypatch.setattr(config, "VAULT_GITSYNC_STAMP", "")
    assert config.stamp_enabled() is True


def test_stamp_enabled_falsey_disables(monkeypatch):
    """A falsey value opts out."""
    for value in ("false", "0", "no", "off"):
        monkeypatch.setattr(config, "VAULT_GITSYNC_STAMP", value)
        assert config.stamp_enabled() is False


def test_stamp_enabled_truthy_enables(monkeypatch):
    monkeypatch.setattr(config, "VAULT_GITSYNC_STAMP", "true")
    assert config.stamp_enabled() is True
