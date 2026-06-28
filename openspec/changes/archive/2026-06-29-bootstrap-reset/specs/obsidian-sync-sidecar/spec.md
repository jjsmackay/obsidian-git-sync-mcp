## ADDED Requirements

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
