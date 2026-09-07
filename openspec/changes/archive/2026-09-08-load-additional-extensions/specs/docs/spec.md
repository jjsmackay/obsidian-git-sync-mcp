## MODIFIED Requirements

### Requirement: Configuration is documented accurately

The README (or a file it links) SHALL document every `VAULT_GIT_*` variable
the code reads and every `VAULT_MCP_*` variable this package itself reads, with
its default, and the upstream `VAULT_*` variables the deployment needs. It SHALL
NOT document a `VAULT_GIT_*` or package-read `VAULT_MCP_*` variable the code does
not read.

#### Scenario: Config table matches the code

- **WHEN** the documented `VAULT_GIT_*` variables are compared with the names
  the code reads
- **THEN** the two sets match exactly

#### Scenario: Package-read VAULT_MCP_* variables match the code

- **WHEN** the documented `VAULT_MCP_*` variables attributed to this package are
  compared with the `VAULT_MCP_*` names the code reads
- **THEN** the two sets match exactly

#### Scenario: Extension-loading trust position is stated

- **WHEN** the documentation for the additional-extension variable is read
- **THEN** it states that a declared extension is fully-trusted in-process code
  running with the server's full privileges
- **AND** it states that extensions load only by explicit declaration, never by
  implicit discovery from installed packages
