# git-sync-extension Specification

## Purpose
TBD - created by archiving change scaffold-extension. Update Purpose after archive.
## Requirements
### Requirement: Extension loads into the MCP server

The git-sync extension SHALL be an `extensions.Extension` subclass
(`GitSyncExtension`) that the upstream `obsidian-web-mcp` server loads in-process
via `serve(extensions=[GitSyncExtension()])`. It SHALL run inside the same
process as the MCP server; it SHALL NOT spawn a separate process or daemon.

#### Scenario: Server boots with the extension registered

- **WHEN** the server is started with `serve(extensions=[GitSyncExtension()])`
- **THEN** the server starts successfully
- **AND** the `GitSyncExtension` instance participates in the server lifecycle
  (its post-start hook runs) without raising

### Requirement: Extension is env-gated and disabled by default

The extension SHALL read all configuration from `VAULT_GIT_*` environment
variables. It SHALL be disabled by default: when the enabling variable is unset
or false, the extension SHALL be a no-op — registering no tools and no routes —
and the MCP server SHALL behave exactly as it does upstream without the
extension.

#### Scenario: Disabled by default is a bootable no-op

- **WHEN** the server starts with no `VAULT_GIT_*` variables set
- **THEN** the extension registers no tools and no routes
- **AND** the server runs identically to an upstream server with no extension
  loaded

#### Scenario: Explicitly disabled

- **WHEN** the enabling `VAULT_GIT_*` variable is set to a false value
- **THEN** the extension registers nothing and performs no git-sync work

### Requirement: Startup validation fails closed

When the extension is enabled, a `validate_gitsync()` check SHALL run once at
startup. If the configuration is invalid (for example a missing or unreadable
repository path, or a malformed remote), the server SHALL refuse to start and
SHALL report a clear error identifying the offending configuration. The
extension SHALL NOT start in a partially-configured state.

#### Scenario: Enabled with valid configuration starts

- **WHEN** the extension is enabled and all required `VAULT_GIT_*` values
  are present and valid
- **THEN** `validate_gitsync()` passes and the server starts

#### Scenario: Enabled with invalid configuration refuses to start

- **WHEN** the extension is enabled but a required configuration value is
  missing or invalid
- **THEN** `validate_gitsync()` fails
- **AND** the server refuses to start, reporting which configuration value is
  missing or invalid

### Requirement: Package provides a console entry point

The package SHALL provide a console entry point that constructs a
`GitSyncExtension`, runs `validate_gitsync()`, and starts the upstream server via
`serve([extension])`. On a validation failure the entry point SHALL log a clear
error and exit non-zero (mirroring the upstream fail-closed pattern) rather than
starting the server.

#### Scenario: Entry point starts the server with the extension

- **WHEN** the console entry point runs with valid configuration
- **THEN** it constructs the extension, passes `validate_gitsync()`, and calls
  `serve([extension])`

#### Scenario: Entry point fails closed on bad configuration

- **WHEN** the console entry point runs with the extension enabled but invalid
  configuration
- **THEN** it logs a clear error and exits non-zero without starting the server

### Requirement: Push credential is configured via VAULT_GIT_TOKEN

The extension SHALL recognise `VAULT_GIT_TOKEN` as the configuration value that
holds the HTTPS push credential, following the existing `VAULT_GIT_*` convention.
When set, it SHALL be the credential used for authenticated git operations via the
env-reading credential helper; the extension SHALL NOT log or echo its value.

#### Scenario: Token is read from the environment

- **WHEN** the extension is enabled and `VAULT_GIT_TOKEN` is set
- **THEN** the configured token is made available to the worker's credential path
- **AND** the token value never appears in logs or error messages

### Requirement: Startup validation fails closed on a missing credential

`validate_gitsync()` SHALL fail closed at startup when the extension is enabled
with a push remote configured and the remote requires a credential that cannot be
resolved. Specifically, when the resolved remote URL uses HTTPS, carries no
embedded credential, and `VAULT_GIT_TOKEN` is unset or empty, the server SHALL
refuse to start and SHALL report that no push credential is configured, without
echoing the remote URL or any secret. An SSH remote, an HTTPS remote that embeds a
credential, or commit-only mode (no push remote) SHALL NOT require `VAULT_GIT_TOKEN`.

#### Scenario: HTTPS remote with no credential refuses to start

- **WHEN** the extension is enabled, the push remote resolves to a tokenless HTTPS
  URL, and `VAULT_GIT_TOKEN` is unset
- **THEN** `validate_gitsync()` fails
- **AND** the server refuses to start, reporting that no push credential is
  configured, without echoing the remote URL

#### Scenario: HTTPS remote with token passes

- **WHEN** the extension is enabled, the push remote resolves to a tokenless HTTPS
  URL, and `VAULT_GIT_TOKEN` is set
- **THEN** `validate_gitsync()` passes the credential check and the server starts

#### Scenario: SSH remote does not require a token

- **WHEN** the extension is enabled and the push remote resolves to an SSH URL
- **THEN** `validate_gitsync()` does not require `VAULT_GIT_TOKEN` and the
  credential check passes

#### Scenario: Commit-only mode does not require a token

- **WHEN** the extension is enabled with no push remote configured (commit-only)
- **THEN** `validate_gitsync()` does not require `VAULT_GIT_TOKEN`

