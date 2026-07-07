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

### Requirement: OAuth client registry persists on a dedicated volume

The mcp service SHALL persist the upstream server's dynamically-registered OAuth
client registry on a dedicated named volume that is separate from the vault
working tree, so registered MCP clients survive a redeploy instead of being
rejected with `invalid_client`. `docker-compose.yml` SHALL define a named volume
mounted on the `mcp` service at `/data` and SHALL set `OAUTH_CLIENTS_PATH` to a
path on that volume (`/data/oauth_clients.json`). The registry SHALL NOT be
placed under the vault path: the git-sync worker sweeps, commits and pushes the
vault tree, and the registry holds per-client secrets, so a location inside the
tree would publish those secrets to the vault's git remote.

#### Scenario: Registry survives a redeploy

- **WHEN** an MCP client has registered via dynamic client registration and the
  mcp service is redeployed
- **THEN** the registry file persists on the dedicated volume and the client's
  `client_id` is still recognised, so it is not rejected with `invalid_client`

#### Scenario: Registry volume is separate from the vault

- **WHEN** the `mcp` service volume mounts and `OAUTH_CLIENTS_PATH` are inspected
- **THEN** the registry path resolves onto a dedicated named volume mounted at
  `/data`, not onto the vault working tree the git-sync worker commits and pushes

### Requirement: OAuth registry volume inherits writable ownership from the image

The mcp image SHALL pre-create the `/data` directory owned by uid 10001 before
the dedicated registry volume is mounted there, so a fresh (root-owned) named
volume inherits container-user ownership on first use and the non-root server can
write the registry without a host-side chown. This mirrors the sidecar's
image-side ownership fix for its config volume; without it the registry save
(`os.open(..., 0o600)` as uid 10001) fails silently and nothing persists.

#### Scenario: Fresh registry volume is writable by the server user

- **WHEN** the mcp service first starts with a fresh named volume mounted at
  `/data`
- **THEN** `/data` is owned by uid 10001 and the server writes
  `oauth_clients.json` (mode 0600) without a host-side chown

#### Scenario: Silent-failure mode is avoided

- **WHEN** the image build is inspected for the `/data` mount point
- **THEN** the directory is created and chowned to uid 10001 in the image, so a
  root-owned fresh volume does not leave the registry save failing silently

### Requirement: Compose declares a named vault volume

`docker-compose.yml` SHALL declare a `vault` entry under its top-level
`volumes:` block, so that setting `VAULT_HOST_PATH` to a bare name (no `/`)
resolves the `mcp` and `obsidian-sync` services' vault mount to a
Compose-managed named volume instead of a host bind mount, without any other
change to the service definitions.

#### Scenario: Named-volume vault mount validates

- **WHEN** `docker compose config` is run with `VAULT_HOST_PATH` set to a bare
  name (no `/`)
- **THEN** it validates with no error and resolves the vault mount to the
  declared `vault` named volume

#### Scenario: Default host bind mount is unaffected

- **WHEN** `docker compose config` is run with `VAULT_HOST_PATH` left at its
  default (`./vault`)
- **THEN** it validates with no error and resolves the vault mount to that
  host path, exactly as before this change

