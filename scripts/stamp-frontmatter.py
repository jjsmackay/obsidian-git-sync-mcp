#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml"]
# ///
"""Upsert created/modified frontmatter timestamps on a markdown file.

Matches the Obsidian Linter plugin's format (YYYY-MM-DDTHH:mm:ssZ, UTC) so
desktop-side stamps and MCP-side stamps don't thrash each other.

- created: set only if missing
- modified: always bumped to now

Non-markdown paths and missing files are skipped silently (deletes).
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

FM_DELIM = "---\n"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TS_PATTERN = re.compile(
    r"^(created|modified): '(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)'$",
    re.MULTILINE,
)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime(TS_FORMAT)


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith(FM_DELIM):
        return None, text
    end = text.find("\n" + FM_DELIM, len(FM_DELIM) - 1)
    if end == -1:
        return None, text
    fm = text[len(FM_DELIM) : end + 1]
    body = text[end + 1 + len(FM_DELIM) :]
    return fm, body


def stamp(path: Path) -> None:
    if not path.is_file() or path.suffix.lower() != ".md":
        return

    original = path.read_text(encoding="utf-8")
    fm_text, body = split_frontmatter(original)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096

    data = yaml.load(fm_text) if fm_text is not None else None
    if data is None:
        data = {}

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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: stamp-frontmatter.py <path> [<path> ...]", file=sys.stderr)
        return 2
    for p in argv[1:]:
        try:
            stamp(Path(p))
        except Exception as e:
            print(f"[stamp-frontmatter] {p}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
