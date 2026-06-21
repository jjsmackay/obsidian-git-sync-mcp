"""Upsert ``created``/``modified`` frontmatter timestamps on MCP-written notes.

Ported from the bobsidian origin ``stamp-frontmatter.py``. The behaviour and its
quirks are deliberate, not incidental:

- ``created`` is set only when missing; ``modified`` is always bumped to now.
- Timestamps use the Obsidian Linter plugin's exact form -- ``YYYY-MM-DDTHH:MM:SSZ``,
  UTC, **unquoted**. ``ruamel.yaml`` quotes scalars that look like times, so we
  emit then strip the quotes with ``TS_PATTERN``. Matching the Linter byte-for-byte
  is what stops desktop-side and server-side stamps from endlessly re-stamping
  each other.
- ``ruamel.yaml`` (not PyYAML) round-trips the rest of the frontmatter preserving
  quotes, key order, and comments, so a user's frontmatter is never reserialised.
- Non-``.md`` paths and missing files are skipped silently (e.g. deletes).
- We write only when content actually changed, and only when the mtime gate opens
  (see ``stamp``), so stamping is idempotent and does not thrash.

This module never raises out to the worker: ``stamp`` catches per-file errors and
``stamp_paths`` is the fail-soft batch door the worker calls.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

FM_DELIM = "---\n"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# ruamel emits times single-quoted; strip the quotes so created/modified land in
# the Linter's unquoted form. Anchored per line via re.MULTILINE.
TS_PATTERN = re.compile(
    r"^(created|modified): '(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)'$",
    re.MULTILINE,
)


def now_utc() -> str:
    """Current UTC time in the Linter format ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(timezone.utc).strftime(TS_FORMAT)


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split ``text`` into (frontmatter, body).

    Returns ``(None, text)`` when there is no leading ``---`` block. Otherwise the
    frontmatter is the text between the delimiters (trailing newline kept) and the
    body is everything after the closing delimiter. Ported verbatim from the origin.
    """
    if not text.startswith(FM_DELIM):
        return None, text
    end = text.find("\n" + FM_DELIM, len(FM_DELIM) - 1)
    if end == -1:
        return None, text
    fm = text[len(FM_DELIM) : end + 1]
    body = text[end + 1 + len(FM_DELIM) :]
    return fm, body


def _modified_epoch(data) -> int | None:
    """Parse ``data['modified']`` (Linter form) to a whole-second UTC epoch.

    Returns None when ``modified`` is absent or not in the Linter form -- both
    cases mean the gate cannot rely on it, so the caller stamps.
    """
    raw = data.get("modified")
    if not raw:
        return None
    try:
        dt = datetime.strptime(str(raw), TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(dt.timestamp())


def stamp(path: Path) -> bool:
    """Stamp one note's frontmatter; return whether it wrote.

    Skips non-``.md`` and missing paths silently (returns False). Applies the
    mtime-vs-``modified`` gate: the file is stamped only when its on-disk mtime,
    floored to whole seconds (the timestamp format's resolution), is strictly
    newer than the current ``modified`` -- or when ``modified`` is absent/
    unparseable. A file already carrying the current second's ``modified`` is left
    byte-unchanged, which is what keeps re-runs and client-supplied stamps from
    thrashing.

    Catches its own errors (e.g. malformed frontmatter that makes ``ruamel`` raise)
    and logs them, returning False rather than propagating -- the worker stays
    fail-soft and the file is still staged/committed unstamped.
    """
    try:
        if not path.is_file() or path.suffix.lower() != ".md":
            return False

        original = path.read_text(encoding="utf-8")
        fm_text, body = split_frontmatter(original)

        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096

        data = yaml.load(fm_text) if fm_text is not None else None
        if data is None:
            data = {}

        # mtime gate: floor mtime to whole seconds and compare to the current
        # modified. floor(mtime) > modified (or modified missing/unparseable) opens
        # the gate. After a stamp, floor(mtime) == modified, so a re-run is a no-op.
        mtime_floor = int(path.stat().st_mtime)
        modified_epoch = _modified_epoch(data)
        if modified_epoch is not None and mtime_floor <= modified_epoch:
            return False

        ts = now_utc()
        if not data.get("created"):
            data["created"] = ts
        data["modified"] = ts

        buf = StringIO()
        yaml.dump(data, buf)
        fm_out = TS_PATTERN.sub(r"\1: \2", buf.getvalue())
        new = f"{FM_DELIM}{fm_out}{FM_DELIM}{body}"

        if new != original:
            path.write_text(new, encoding="utf-8")
            return True
        return False
    except Exception:
        logger.exception("frontmatter stamping failed for %s", path)
        return False


def stamp_paths(paths) -> None:
    """Stamp each path, fail-soft per file (never raises).

    The worker's door into stamping: a single bad file must never stop the commit,
    so every per-path error is caught and logged here too (belt-and-braces with
    ``stamp``'s own guard).
    """
    for p in paths:
        try:
            stamp(Path(p))
        except Exception:
            logger.exception("frontmatter stamping failed for %s", p)
