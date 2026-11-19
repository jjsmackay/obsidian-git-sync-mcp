# Spec Delta

## ADDED Requirements

### Requirement: Optional nested sidecar syncs one folder to its own remote

The stack SHALL offer an optional `obsidian-sync-nested` service, gated behind the
Compose profile `nested`, that runs the sidecar image against one folder of the
vault and syncs it to a separate remote vault. It SHALL mount the same vault
working tree as the main sidecar, take the folder from `NESTED_SYNC_SUBPATH`
(relative to the vault root), persist its `ob` state on its own named volume, and
run with settings (`.obsidian`) sync off.

#### Scenario: Nested service is off by default

- **WHEN** `docker compose config` is run without the `nested` profile
- **THEN** the resolved services do not include `obsidian-sync-nested`

#### Scenario: Nested service targets the folder with its own state

- **WHEN** `docker compose --profile obsidian --profile nested config` is run with
  `NESTED_SYNC_SUBPATH` set
- **THEN** `obsidian-sync-nested` has `VAULT_PATH` set to that folder inside the
  vault, a config volume distinct from the main sidecar's, and settings sync off

### Requirement: Nested sidecar refuses a path outside the vault

When `NESTED_PARENT` is set, the entry point and `bootstrap` SHALL refuse to run,
with a reason, unless `VAULT_PATH` is an existing directory strictly inside
`NESTED_PARENT`. When `NESTED_PARENT` is unset the check SHALL do nothing.

#### Scenario: Empty subpath is refused

- **WHEN** `NESTED_PARENT` is set and `VAULT_PATH` resolves to `NESTED_PARENT`
  itself
- **THEN** the sidecar exits with a message naming both paths and does not sync

#### Scenario: Path outside the vault is refused

- **WHEN** `VAULT_PATH` resolves outside `NESTED_PARENT` (e.g. via `../`)
- **THEN** the sidecar exits with a message and does not sync

#### Scenario: Main sidecar unaffected

- **WHEN** `NESTED_PARENT` is unset
- **THEN** the entry point and `bootstrap` behave exactly as before

### Requirement: Bootstrap applies optional sync settings

`bootstrap` SHALL use `SYNC_DEVICE_NAME` as the device name, defaulting to
`headless`. When `SYNC_CONFIGS` or `SYNC_FILE_TYPES` is set, including set to an
empty value, `bootstrap` SHALL apply it with `ob sync-config` after `sync-setup`.
When either is unset, `bootstrap` SHALL leave that setting at `ob`'s default.

#### Scenario: Settings applied when set

- **WHEN** `bootstrap` runs with `SYNC_CONFIGS` set to an empty value
- **THEN** `ob sync-status` afterwards reports config syncing disabled

#### Scenario: Defaults kept when unset

- **WHEN** `bootstrap` runs with none of the three variables set
- **THEN** the device name is `headless` and `ob`'s default settings are unchanged
