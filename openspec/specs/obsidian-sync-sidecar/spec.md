# obsidian-sync-sidecar Specification

## Purpose
TBD - created by archiving change obsidian-sync-sidecar. Update Purpose after archive.
## Requirements
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

### Requirement: Idle sidecar auto-starts sync once bootstrapped

When the sidecar starts un-bootstrapped (no config in the persisted config dir) and no explicit command is given, the entry point SHALL print the bootstrap instructions once and then poll for config rather than idling forever. As soon
as the config dir becomes non-empty — i.e. an operator has run the explicit
`bootstrap` against the running container — the entry point SHALL start
continuous sync itself (`ob sync --path "$VAULT_PATH" --continuous`) without a
manual container restart. The poll interval SHALL default to a few seconds and
SHALL be overridable via an environment variable. The entry point SHALL NOT
auto-run bootstrap: it only auto-starts sync once config exists, preserving the
explicit-only bootstrap contract (a detected TTY must not trigger an interactive
login). The existing branches — explicit `bootstrap` arg / `BOOTSTRAP` env,
explicit passthrough command, and already-bootstrapped → continuous sync — SHALL
be unchanged.

#### Scenario: Idle entry point begins syncing after bootstrap without a restart

- **WHEN** the sidecar starts with no config and no explicit command, an operator
  then runs the explicit `bootstrap` against the running container, and the config
  dir becomes non-empty
- **THEN** the entry point detects the config on its next poll and execs
  `ob sync --path "$VAULT_PATH" --continuous`, with no manual container restart

#### Scenario: Instructions are printed once, then the loop idles quietly

- **WHEN** the sidecar starts un-bootstrapped
- **THEN** the bootstrap instructions are printed a single time
- **AND** the entry point sleeps the poll interval between `is_bootstrapped`
  checks rather than executing `sleep infinity`

#### Scenario: Poll interval is overridable

- **WHEN** the poll-interval environment variable is set
- **THEN** the entry point waits that interval between config checks
- **AND** when it is unset the entry point uses its built-in default of a few
  seconds

#### Scenario: Bootstrap is never auto-run

- **WHEN** the sidecar is idle and un-bootstrapped, even with a TTY attached
- **THEN** the entry point only ever auto-starts sync after config appears
- **AND** it never invokes `bootstrap` itself

#### Scenario: Existing start branches are preserved

- **WHEN** a `bootstrap` arg / `BOOTSTRAP` env, an explicit passthrough command,
  or an already-populated config dir is present at start
- **THEN** the entry point behaves exactly as before — interactive bootstrap, the
  verbatim command, or continuous sync respectively — without entering the poll
  loop

### Requirement: Bootstrap supports a destructive --reset for account switching

The bootstrap command SHALL accept a `--reset` flag that wipes the persisted `ob`
configuration and sync state before running the normal bootstrap flow, so an
operator can switch the sidecar to a different Obsidian account in place. Because
the wipe discards credentials and sync state, `--reset` SHALL prompt for explicit
confirmation and abort without deleting anything if confirmation is not given. The
config location SHALL be derived the same way the entry point derives it
(`${HOME:-/home/ob}/.config/obsidian-headless`) and the path SHALL be guarded
(non-empty, not `/`, an existing directory) before any removal. After a confirmed
wipe the command SHALL fall through to the unchanged login → sync-setup → status
flow, including the hidden end-to-end password read. With no arguments the command
SHALL behave exactly as before; an unrecognised flag SHALL print a short usage
message and exit non-zero.

#### Scenario: Reset wipes config then bootstraps a fresh account

- **WHEN** an operator runs `bootstrap --reset` against a sidecar already
  configured for one account and confirms the prompt
- **THEN** the persisted config/state under the config directory is removed
- **AND** the command then runs the normal `ob login` → `sync-setup` → status flow
  so a different account/vault can be configured

#### Scenario: Reset requires explicit confirmation

- **WHEN** `bootstrap --reset` prompts for confirmation and the operator answers
  with anything other than the expected confirmation
- **THEN** nothing is deleted and the command exits without changing the config

#### Scenario: Config path is guarded before removal

- **WHEN** `--reset` is about to wipe the config directory
- **THEN** it removes only contents under the resolved config directory and never
  runs against an empty path or `/`

#### Scenario: No-arg bootstrap is unchanged

- **WHEN** `bootstrap` is run with no arguments
- **THEN** it runs the existing login → sync-setup → status flow with no wipe and
  no confirmation prompt

#### Scenario: Unknown flag errors with usage

- **WHEN** `bootstrap` is run with an unrecognised flag
- **THEN** it prints a short usage message and exits non-zero without logging in

