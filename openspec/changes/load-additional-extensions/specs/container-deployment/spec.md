## MODIFIED Requirements

### Requirement: Env-example documents the full surface

`.env.example` SHALL document the upstream `VAULT_*` variables the deployment
needs, ALL `VAULT_GIT_*` variables the code reads, and ALL `VAULT_MCP_*`
variables this package itself reads, using the finalised names, with the
extension disabled by default and no additional extensions declared.

#### Scenario: Every code-read VAULT_GIT_* var is documented

- **WHEN** `.env.example` is compared with the `VAULT_GIT_*` names the code reads
- **THEN** every variable the code reads appears in `.env.example`, and no
  documented `VAULT_GIT_*` name is one the code never reads

#### Scenario: Every code-read VAULT_MCP_* var is documented

- **WHEN** `.env.example` is compared with the `VAULT_MCP_*` names this package
  reads
- **THEN** every such variable appears in `.env.example`, and no documented
  `VAULT_MCP_*` name attributed to this package is one it never reads

#### Scenario: Safe defaults

- **WHEN** a deployment copies `.env.example` to `.env` without editing the
  git-sync section
- **THEN** the extension is disabled (a bootable no-op) rather than half-configured
- **AND** no additional extensions are declared, so the server loads
  `GitSyncExtension` alone
