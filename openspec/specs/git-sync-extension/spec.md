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

The extension SHALL read all configuration from `VAULT_GITSYNC_*` environment
variables. It SHALL be disabled by default: when the enabling variable is unset
or false, the extension SHALL be a no-op — registering no tools and no routes —
and the MCP server SHALL behave exactly as it does upstream without the
extension.

#### Scenario: Disabled by default is a bootable no-op

- **WHEN** the server starts with no `VAULT_GITSYNC_*` variables set
- **THEN** the extension registers no tools and no routes
- **AND** the server runs identically to an upstream server with no extension
  loaded

#### Scenario: Explicitly disabled

- **WHEN** the enabling `VAULT_GITSYNC_*` variable is set to a false value
- **THEN** the extension registers nothing and performs no git-sync work

### Requirement: Startup validation fails closed

When the extension is enabled, a `validate_gitsync()` check SHALL run once at
startup. If the configuration is invalid (for example a missing or unreadable
repository path, or a malformed remote), the server SHALL refuse to start and
SHALL report a clear error identifying the offending configuration. The
extension SHALL NOT start in a partially-configured state.

#### Scenario: Enabled with valid configuration starts

- **WHEN** the extension is enabled and all required `VAULT_GITSYNC_*` values
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

