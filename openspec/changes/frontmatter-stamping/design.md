## Context

The git-worker change left a marked seam in `_handle_mcp_write`: stamp the paths
before staging so the stamp lands in the same commit. This change fills that
seam by porting the origin `stamp-frontmatter.py`, adding the mtime-vs-`modified`
gate the HANDOFF specifies.

The origin used `ruamel.yaml` deliberately, not PyYAML / python-frontmatter:
it round-trips frontmatter preserving quotes, key order, and comments, and it can
emit the Linter's exact unquoted timestamp form (`ruamel` quotes timestamps by
default, so the origin post-processes with a regex to strip the quotes). Matching
the Linter byte-for-byte is what stops desktop edits and server edits from
endlessly re-stamping each other.

## Goals / Non-Goals

**Goals:**

- A `stamp(path)` that ports the origin logic: created-if-missing,
  modified-always, Linter format, formatting-preserving, skip non-`.md`/missing.
- The mtime-vs-`modified` gate at 1-second granularity (the timestamp format's
  resolution), making stamping idempotent.
- Integration at the worker's MCP-write seam, gated by `VAULT_GITSYNC_STAMP`.

**Non-Goals:**

- No stamping on sweeps (device edits arrive already stamped; re-stamping them
  server-side is the thrash we explicitly avoid).
- No new timestamp semantics beyond created/modified.
- No `state.db` / authorship (v2).

## Decisions

**Stamp MCP-write paths only, not sweeps.** Device edits reach the vault already
stamped by the desktop Linter and are committed by the sweep path, which never
calls the stamper — so they are "skipped" exactly as the HANDOFF describes,
without server-side churn. MCP writes are the only thing we stamp, matching the
origin. The mtime gate is still applied to MCP paths so a client that supplies
its own current `modified` is not double-bumped and re-runs are idempotent.

**1-second gate granularity.** Filesystem mtime has sub-second precision; the
timestamp format is whole seconds. Comparing raw mtime against the second-granular
`modified` would make every just-stamped file look "newer" by a fraction and
re-stamp forever. Flooring mtime to whole seconds before the comparison closes
that loop: after stamping, `floor(mtime) == modified`, so the gate skips it.

**`ruamel.yaml`, with the quote-stripping post-process, ported verbatim.** It is
the only way to preserve arbitrary user frontmatter while emitting the Linter's
unquoted timestamps. Alternative considered: python-frontmatter (already a
transitive dep). Rejected — PyYAML reserialises and drops comments/quote style,
which would rewrite users' frontmatter and reintroduce thrash.

**Faithful "inject frontmatter if absent", behind a default-on toggle.** The
origin adds a frontmatter block to a `.md` that has none. That is invasive for a
general tool, so the whole behaviour sits behind `VAULT_GITSYNC_STAMP` (default
enabled, matching the project's purpose); operators who do not use timestamp
frontmatter disable it and their files are committed untouched.

## Risks / Trade-offs

- [Stamping injects frontmatter into a note that had none] → Documented; gated by
  `VAULT_GITSYNC_STAMP`. Default-on matches the project's first user; off is a
  one-line opt-out.
- [A malformed existing frontmatter block could make `ruamel` raise] → `stamp()`
  catches per-file and logs, never propagating (the worker stays fail-soft); the
  file is still staged and committed unstamped rather than lost.
- [Clock skew between the writing host and the mtime source] → Both come from the
  same host (the server writes the file and reads its mtime), so skew is not a
  factor here.
