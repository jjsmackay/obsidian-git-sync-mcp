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
needs and ALL `VAULT_GIT_*` variables the code reads, using the finalised
names, with the extension disabled by default.

#### Scenario: Every code-read VAULT_GIT_* var is documented

- **WHEN** `.env.example` is compared with the `VAULT_GIT_*` names the code reads
- **THEN** every variable the code reads appears in `.env.example`, and no
  documented `VAULT_GIT_*` name is one the code never reads

#### Scenario: Safe defaults

- **WHEN** a deployment copies `.env.example` to `.env` without editing the
  git-sync section
- **THEN** the extension is disabled (a bootable no-op) rather than half-configured

### Requirement: Image supports SSH deploy-key git transport

The mcp image SHALL include an SSH client so the git-sync worker can push over an
`ssh` remote when a deploy key is mounted. Git's SSH transport invokes an `ssh`
binary, which is only a Recommends of `git` and is therefore dropped by
`--no-install-recommends`; the image SHALL install it explicitly.

#### Scenario: ssh available in the image

- **WHEN** `ssh -V` is run inside the built mcp image
- **THEN** it reports an SSH client version (git's SSH transport dependency is present)

#### Scenario: Token path unaffected

- **WHEN** the vault uses a token-bearing https remote (no SSH)
- **THEN** pushing works without any SSH client involvement

### Requirement: Compose documents both push-credential mechanisms

`docker-compose.yml` SHALL document, opt-in (commented out by default), the two ways to
supply the worker's push credential without baking it into the image: a token-bearing
https remote (no mount needed; the token lives in the vault's `.git/config`) and an SSH
deploy-key mount paired with `GIT_SSH_COMMAND`.

#### Scenario: SSH deploy-key path is documented and ready to enable

- **WHEN** the `mcp` service definition is inspected
- **THEN** it carries a commented, ready-to-uncomment SSH deploy-key volume mount and a
  `GIT_SSH_COMMAND` environment entry

#### Scenario: Token path requires no compose change

- **WHEN** the token-in-https-URL mechanism is used
- **THEN** the compose file documents that no mount is required (the credential lives in
  the vault working tree's `.git/config`)

### Requirement: Named vault volume must be seeded and chowned

A fresh Docker named volume used for the vault SHALL mount root-owned, so it cannot
be cloned into on the host and the uid-10001 container user cannot commit until it is
fixed. The deployment SHALL document seeding such a volume with a one-off container
that clones the repo into it and runs `chown -R 10001:10001` on the vault path, so the
non-root container user can commit. Unlike the sidecar's `config` volume, the vault
volume has no image-side ownership fix; the seed step is the documented remedy.

#### Scenario: Fresh named vault volume is seeded for the container user

- **WHEN** the vault is a fresh Docker named volume rather than a host directory
- **THEN** the docs describe a one-off container that clones the repo into the volume
  and runs `chown -R 10001:10001` on the vault path so uid 10001 can commit

