## ADDED Requirements

### Requirement: ob runs headless in the sidecar image

The sidecar image SHALL install `obsidian-headless` and provide a working `ob`
command that runs in the slim container without a display. The image build SHALL
satisfy `better-sqlite3`'s native requirements.

#### Scenario: Sidecar image builds

- **WHEN** the sidecar image is built
- **THEN** the build completes with `obsidian-headless` installed

#### Scenario: ob is invocable headless

- **WHEN** `ob --help` (or the CLI's version/help command) is run inside the built
  image
- **THEN** it runs successfully and prints its usage, with no display required

### Requirement: Sidecar is opt-in via a Compose profile

The `obsidian-sync` service SHALL be gated behind the Compose profile `obsidian`.
A plain `docker compose up` SHALL start only the `mcp` service; the sidecar SHALL
start only when the `obsidian` profile is selected.

#### Scenario: Default up excludes the sidecar

- **WHEN** `docker compose config` is run with no profile
- **THEN** the resolved services do not include `obsidian-sync`

#### Scenario: Profile selects the sidecar

- **WHEN** `docker compose --profile obsidian config` is run
- **THEN** the resolved services include both `mcp` and `obsidian-sync`

### Requirement: Persisted state and shared vault

The `obsidian-sync` service SHALL persist `ob`'s configuration and sync state
(under `~/.config/obsidian-headless/`) on a named volume so credentials and
`state.db` survive restarts, and SHALL mount the same vault working tree the
`mcp` service uses so device edits and git sync operate on one tree.

#### Scenario: Config persists across restarts

- **WHEN** the sidecar's `ob` config directory is inspected
- **THEN** it is backed by a named volume (not the container's ephemeral layer)

#### Scenario: Vault is shared with mcp

- **WHEN** the `obsidian-sync` and `mcp` service volume mounts are compared
- **THEN** both mount the same vault working tree

### Requirement: Documented bootstrap

The change SHALL document the one-time interactive bootstrap (account login and
sync setup) using the CLI's actual subcommands, run via `docker compose run`
against the persisted volume, and the long-running command the service uses.

#### Scenario: Bootstrap steps are documented and match the CLI

- **WHEN** an operator follows the documented bootstrap
- **THEN** the commands shown are the ones `ob` actually provides (login + sync
  setup) and write into the persisted config volume
