# container-deployment Specification

## Purpose
TBD - created by archiving change container-deployment. Update Purpose after archive.
## Requirements
### Requirement: Image runs the extension-loaded server

The `Dockerfile` SHALL build an image that installs this package and the
upstream server and, by default, runs the console entry point that starts the
upstream server with the `GitSyncExtension` loaded. The image SHALL include the
`git` binary, since the worker invokes it at runtime.

#### Scenario: Image builds

- **WHEN** the image is built from the `Dockerfile`
- **THEN** the build completes successfully with this package and its
  dependencies installed

#### Scenario: git available in the image

- **WHEN** `git --version` is run inside the built image
- **THEN** it reports a git version (the worker's dependency is present)

#### Scenario: Default command is the extension entry point

- **WHEN** the image's default command is inspected
- **THEN** it runs the `obsidian-git-sync-mcp` console entry point

### Requirement: Compose mcp service

`docker-compose.yml` SHALL define an `mcp` service that builds the image, reads
configuration from `.env`, mounts the vault working tree as a volume, publishes
only the MCP port, sets a restart policy, and defines a `HEALTHCHECK`. The
compose file SHALL be valid.

#### Scenario: Compose config validates

- **WHEN** `docker compose config` is run against the file with a populated `.env`
- **THEN** it validates with no error and resolves the `mcp` service

#### Scenario: Only the MCP port is published

- **WHEN** the `mcp` service port mapping is inspected
- **THEN** only the MCP port is published to the host (no other service ports)

### Requirement: Healthcheck on the MCP port

The `mcp` service `HEALTHCHECK` SHALL verify that the MCP port is accepting TCP
connections, using only what is already in the image (no extra packages), since
upstream serves no usable inbound health route.

#### Scenario: Healthy when listening

- **WHEN** the server is up and listening on the MCP port
- **THEN** the healthcheck command succeeds (exit 0)

#### Scenario: Unhealthy when not listening

- **WHEN** nothing is listening on the MCP port
- **THEN** the healthcheck command fails (non-zero exit)

### Requirement: Env-example documents the full surface

`.env.example` SHALL document the upstream `VAULT_*` variables the deployment
needs and ALL `VAULT_GITSYNC_*` variables the code reads, using the finalised
names, with the extension disabled by default.

#### Scenario: Every code-read VAULT_GITSYNC_* var is documented

- **WHEN** `.env.example` is compared with the `VAULT_GITSYNC_*` names the code reads
- **THEN** every variable the code reads appears in `.env.example`, and no
  documented `VAULT_GITSYNC_*` name is one the code never reads

#### Scenario: Safe defaults

- **WHEN** a deployment copies `.env.example` to `.env` without editing the
  git-sync section
- **THEN** the extension is disabled (a bootable no-op) rather than half-configured

