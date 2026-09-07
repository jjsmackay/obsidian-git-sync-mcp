## MODIFIED Requirements

### Requirement: Extension loads into the MCP server

The git-sync extension SHALL be an `extensions.Extension` subclass
(`GitSyncExtension`) that the upstream `obsidian-web-mcp` server loads in-process
via `serve(...)`, as the first element of the extension list and ahead of any
additional operator-declared extensions. It SHALL run inside the same process as
the MCP server; it SHALL NOT spawn a separate process or daemon.

#### Scenario: Server boots with the extension registered

- **WHEN** the server is started with `serve(extensions=[GitSyncExtension()])`
- **THEN** the server starts successfully
- **AND** the `GitSyncExtension` instance participates in the server lifecycle
  (its post-start hook runs) without raising

#### Scenario: Server boots with additional extensions alongside git-sync

- **WHEN** the server is started with `GitSyncExtension` followed by one or more
  operator-declared extensions
- **THEN** the server starts successfully
- **AND** `GitSyncExtension` is the first extension in the list, so its hook runs
  before any additional extension's at each lifecycle stage
- **AND** git-sync behaviour is unchanged from the single-extension case
