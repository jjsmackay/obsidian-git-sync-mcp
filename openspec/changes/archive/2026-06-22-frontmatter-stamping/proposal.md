## Why

The worker commits MCP writes, but the commit captures the file as the client
sent it — with no `modified` timestamp bumped. The bobsidian origin stamped
`created`/`modified` frontmatter on every MCP-written `.md` so history (and the
vault itself) carried accurate edit times, in the exact format the Obsidian
Linter plugin uses (`YYYY-MM-DDTHH:mm:ssZ`, UTC, unquoted) so desktop-side and
server-side stamps never thrash. This change ports that stamping into the
worker's MCP-write pipeline, plus the mtime-vs-`modified` gate that keeps it
idempotent.

## What Changes

- Add a `frontmatter-stamping` capability porting the origin `stamp-frontmatter.py`:
  - `created` set only when missing; `modified` always bumped to now.
  - Timestamp format `YYYY-MM-DDTHH:MM:SSZ` (UTC, **unquoted**), matching the
    Obsidian Linter, using `ruamel.yaml` to preserve existing frontmatter
    formatting, quotes, and comments.
  - Non-`.md` and missing paths skipped silently.
- Add the **mtime-vs-`modified` gate**: a file is stamped only when its on-disk
  mtime (floored to whole seconds, the format's resolution) is newer than its
  current frontmatter `modified`. This makes stamping idempotent — a file already
  carrying the current second's `modified` is left untouched, so re-runs and
  client-supplied stamps don't thrash.
- Insert stamping into the worker's `MCP_WRITE` handler (the marked seam): stamp
  the event's `.md` paths **before staging**, for every operation except
  `deleted`, so the stamp lands in the same `mcp:` commit. Sweeps are not stamped
  — device edits arrive already stamped by the desktop Linter and flow through
  the sweep untouched (exactly the "device edits skipped" behaviour the gate
  describes).
- Gate the whole behaviour behind `VAULT_GITSYNC_STAMP` (default enabled); off
  leaves MCP-written files exactly as the client sent them.

## Capabilities

### New Capabilities
- `frontmatter-stamping`: the stamp logic (created/modified upsert, Linter
  format, formatting-preserving), the mtime-vs-`modified` gate, and its
  integration into the worker's MCP-write commit pipeline.

### Modified Capabilities
<!-- None. Stamping is inserted at the worker's existing MCP_WRITE seam as
     additive behaviour; the git-worker requirements are unchanged. -->

## Impact

- New code: `stamping.py` (the porter); a call into it from the worker's
  `_handle_mcp_write` before staging.
- New dependency: `ruamel.yaml` (formatting-preserving YAML, as the origin used).
- New `VAULT_GITSYNC_*` config: `STAMP` toggle (provisional name).
- Behaviour note: when enabled, stamping **adds** a frontmatter block to an
  MCP-written `.md` that has none (faithful to the origin). Operators who do not
  use timestamp frontmatter set `VAULT_GITSYNC_STAMP=false`.
