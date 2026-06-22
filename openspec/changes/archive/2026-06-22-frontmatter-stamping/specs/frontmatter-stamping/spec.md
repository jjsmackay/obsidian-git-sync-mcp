## ADDED Requirements

### Requirement: Frontmatter timestamp upsert

Stamping a `.md` file SHALL set `created` only when it is missing and SHALL
always bump `modified` to the current UTC time. Timestamps SHALL use the format
`YYYY-MM-DDTHH:MM:SSZ` (UTC), written **unquoted**, matching the Obsidian Linter
plugin. Existing frontmatter formatting, quoting, and comments SHALL be preserved
(no wholesale reserialisation). Non-`.md` paths and missing files SHALL be
skipped silently.

#### Scenario: New modified, preserved created

- **WHEN** a `.md` file with frontmatter already containing `created` is stamped
- **THEN** `created` is unchanged and `modified` is set to the current UTC
  timestamp in `YYYY-MM-DDTHH:MM:SSZ` form, unquoted

#### Scenario: Created added when missing

- **WHEN** a `.md` file whose frontmatter lacks `created` is stamped
- **THEN** `created` is set to the current timestamp alongside `modified`

#### Scenario: Non-markdown and missing skipped

- **WHEN** stamping is asked to stamp a non-`.md` path or a path that does not exist
- **THEN** nothing is written and no error is raised

### Requirement: mtime-versus-modified gate

A file SHALL be stamped only when its on-disk modification time, floored to whole
seconds, is strictly newer than the timestamp in its current frontmatter
`modified`. A file whose `modified` already equals or exceeds its floored mtime
SHALL be left untouched. A file with no `modified` value SHALL be stamped.

#### Scenario: Already-current file is not re-stamped

- **WHEN** a file already carries a `modified` equal to its floored mtime second
- **THEN** stamping leaves the file unchanged (idempotent; no thrash)

#### Scenario: Stale or absent modified is stamped

- **WHEN** a file's floored mtime is newer than its `modified`, or it has no
  `modified`
- **THEN** the file is stamped

### Requirement: Stamping integrated into the MCP-write commit

When stamping is enabled, the worker SHALL stamp an `MCP_WRITE` event's `.md`
paths before staging them, for every operation except `deleted`, so the stamp is
part of the same `mcp:` commit. `SYNC_SWEEP` events SHALL NOT trigger stamping.
When stamping is disabled, the worker SHALL stage MCP-written files exactly as
received.

#### Scenario: MCP write is stamped within its commit

- **WHEN** stamping is enabled and an `MCP_WRITE` for operation "updated" on a
  `.md` file is processed
- **THEN** the file is stamped and the resulting `mcp:` commit includes the
  stamped frontmatter

#### Scenario: Deletes are not stamped

- **WHEN** an `MCP_WRITE` for operation "deleted" is processed
- **THEN** no stamping is attempted

#### Scenario: Disabled stamping leaves files as received

- **WHEN** `VAULT_GITSYNC_STAMP` is disabled and an `MCP_WRITE` is processed
- **THEN** the committed file is byte-identical to what the client wrote
