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
  and how to enable git sync (`VAULT_GIT_ENABLED`)

#### Scenario: Architecture is explained

- **WHEN** a reader reaches the architecture section
- **THEN** it describes the upstream server + in-process `GitSyncExtension`, the
  `mcp:`/`sync:` commit split, the single git worker, and the 2-container topology

### Requirement: Configuration is documented accurately

The README (or a file it links) SHALL document every `VAULT_GIT_*` variable
the code reads, with its default, and the upstream `VAULT_*` variables the
deployment needs. It SHALL NOT document a `VAULT_GIT_*` variable the code
does not read.

#### Scenario: Config table matches the code

- **WHEN** the documented `VAULT_GIT_*` variables are compared with the names
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

### Requirement: Git repo bootstrap is documented

The README SHALL document how to seed the vault git repo before enabling git sync,
including the fail-closed precondition and both push-credential mechanisms. The worker
commits against an existing tree and never clones, and startup is fail-closed, so the
docs must make seeding an explicit prerequisite.

#### Scenario: Fail-closed precondition is stated

- **WHEN** a reader consults the bootstrap section
- **THEN** it states that with `VAULT_GIT_ENABLED=true` the container refuses to boot if
  the vault is not a git working tree or the configured remote is missing, so the repo
  must be seeded first

#### Scenario: An operator can bootstrap the git repo from the README

- **WHEN** an operator follows the bootstrap section
- **THEN** it walks them through cloning the vault into `VAULT_HOST_PATH`, choosing a
  push credential (token-in-https-URL or SSH deploy key), and then enabling git sync

#### Scenario: Ordering with the obsidian-sync bootstrap is given

- **WHEN** both the git repo and the obsidian-sync sidecar need bootstrapping
- **THEN** the README states the git tree is established first, then the `ob` bootstrap
  runs against the same vault path

### Requirement: Worker commit identity is documented

The README SHALL document that the git-sync worker needs a commit identity, because
git refuses to commit without one and every sweep commit otherwise fails (e.g.
`git-worker sweep commit failed (rc=128)`). It SHALL state the two ways to supply it:
set `VAULT_GIT_GIT_AUTHOR_NAME` and `VAULT_GIT_GIT_AUTHOR_EMAIL` in `.env`, or
configure `user.name`/`user.email` in the vault's own git config.

#### Scenario: Commit identity requirement is stated

- **WHEN** a reader consults the bootstrap docs
- **THEN** it states the worker needs a commit identity and gives both ways to set it
  (the `VAULT_GIT_GIT_AUTHOR_*` env vars or the vault's git config)

### Requirement: Bootstrap ordering and re-bootstrap are documented

The README SHALL document the ordering between establishing the git tree and the
sidecar's `ob` bootstrap, and SHALL document how to re-bootstrap the sidecar to switch
accounts. The git tree (working tree + remote) SHALL be established first, then the
one-time `ob` bootstrap runs against the same vault path; the push credential SHALL be
set before the sidecar first syncs content down. Re-bootstrapping SHALL be documented
as `bootstrap --reset`, which confirms before discarding the stored login and sync
state and then falls through to the normal login → sync-setup → status flow, with
continuous sync auto-starting for the new account afterwards (no manual restart).

#### Scenario: Bootstrap ordering is documented

- **WHEN** both the git tree and the sidecar need bootstrapping
- **THEN** the README states the git tree is established first, then the `ob` bootstrap
  runs against the same vault path, with the push credential set before the first sync

#### Scenario: Re-bootstrap path is documented

- **WHEN** an operator needs to switch the sidecar to a different account
- **THEN** the docs describe `bootstrap --reset` wiping the stored config after
  confirmation and re-running the normal bootstrap flow, with sync auto-starting after

