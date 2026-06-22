# docs Specification

## Purpose
TBD - created by archiving change docs. Update Purpose after archive.
## Requirements
### Requirement: README covers the operator and contributor path

`README.md` SHALL document what the project is and how it differs, the
architecture in brief, a Docker quickstart, the configuration surface, the
optional Obsidian Sync sidecar, safe exposure, monitoring, and development. It
SHALL be accurate to the shipped code and stack.

#### Scenario: An operator can deploy from the README

- **WHEN** an operator reads `README.md`
- **THEN** it shows copying `.env.example` to `.env` and `docker compose up -d`,
  and how to enable git sync (`VAULT_GITSYNC_ENABLED`)

#### Scenario: Architecture is explained

- **WHEN** a reader reaches the architecture section
- **THEN** it describes the upstream server + in-process `GitSyncExtension`, the
  `mcp:`/`sync:` commit split, the single git worker, and the 2-container topology

### Requirement: Configuration is documented accurately

The README (or a file it links) SHALL document every `VAULT_GITSYNC_*` variable
the code reads, with its default, and the upstream `VAULT_*` variables the
deployment needs. It SHALL NOT document a `VAULT_GITSYNC_*` variable the code
does not read.

#### Scenario: Config table matches the code

- **WHEN** the documented `VAULT_GITSYNC_*` variables are compared with the names
  the code reads
- **THEN** the two sets match exactly

### Requirement: Exposure and monitoring are documented

The README SHALL state that only the MCP port is published and document safe
remote exposure (reverse proxy / Cloudflare Tunnel / Tailscale) including
`VAULT_MCP_ALLOWED_HOSTS` / `VAULT_MCP_PUBLIC_URL`, and SHALL describe the three
monitoring layers (container healthcheck, upstream liveness heartbeat, git-sync
push heartbeat).

#### Scenario: Exposure guidance is present

- **WHEN** a reader looks for how to reach the server remotely
- **THEN** the README documents putting it behind a proxy/tunnel and setting the
  allowed-hosts / public-URL variables, with no tunnel baked into the project

#### Scenario: Monitoring layers are distinguished

- **WHEN** a reader looks for monitoring
- **THEN** the README distinguishes the container healthcheck, the upstream
  server-liveness heartbeat, and the git-sync push heartbeat

