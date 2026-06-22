## 1. Dependency & config

- [x] 1.1 Add `ruamel.yaml` to `pyproject.toml` dependencies; `uv sync`
- [x] 1.2 Add `VAULT_GITSYNC_STAMP` config (default enabled); accessor `stamp_enabled()` mirroring `is_enabled()` truthy parsing

## 2. Stamper

- [x] 2.1 Add `stamping.py` porting the origin `stamp-frontmatter.py`: `split_frontmatter`, created-if-missing / modified-always, `ruamel.yaml` round-trip with `preserve_quotes`, the `TS_PATTERN` quote-strip to emit unquoted `YYYY-MM-DDTHH:MM:SSZ`, write only when content changed
- [x] 2.2 Skip non-`.md` and missing paths silently; catch per-file errors and log (never raise — worker stays fail-soft)
- [x] 2.3 Add the mtime-vs-`modified` gate: read floored-to-seconds mtime, parse current `modified`; stamp only when `floor(mtime) > modified` (or `modified` absent)

## 3. Worker integration

- [x] 3.1 In `_handle_mcp_write` (at the marked seam), when `stamp_enabled()` and operation != "deleted": stamp the event's paths before `git.add(...)` so the stamp is in the same commit
- [x] 3.2 Keep it fail-soft: a stamping error logs and the write still stages/commits unstamped

## 4. Tests

- [x] 4.1 created preserved when present; created added when absent; modified always bumped; format is unquoted `YYYY-MM-DDTHH:MM:SSZ`
- [x] 4.2 Existing frontmatter quoting/comments/key-order preserved (round-trip a file with comments + a quoted field)
- [x] 4.3 Non-`.md` path and missing path → no write, no raise
- [x] 4.4 Gate: a file whose `modified` equals its floored mtime is NOT re-stamped (idempotent — stamp twice, unchanged the second time); stale/absent `modified` IS stamped
- [x] 4.5 Worker: an enabled `MCP_WRITE` "updated" on a `.md` produces an `mcp:` commit whose committed content carries the bumped `modified`
- [x] 4.6 Worker: operation "deleted" does not stamp; `SYNC_SWEEP` does not stamp
- [x] 4.7 Worker: `VAULT_GITSYNC_STAMP=false` → committed file byte-identical to what was written
- [x] 4.8 A malformed frontmatter file is logged and still committed (unstamped), worker alive

## 5. Validation

- [x] 5.1 Run `openspec validate frontmatter-stamping --strict` and resolve findings
- [x] 5.2 Confirm `uv run pytest` passes (all prior tests + new ones)
