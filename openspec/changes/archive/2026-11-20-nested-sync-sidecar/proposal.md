# Proposal

## Why

Some deployments need one folder of the vault shared with people who must not
see the rest: a team folder inside a private vault. Obsidian Sync shares whole
remote vaults, not folders, so the folder needs its own remote vault, and
something has to keep the folder on disk and that remote in step.

A second `ob` client pointed at the folder does this. It was tested against two
real remote vaults (one for the whole vault, one for the folder) with four
simulated devices: edits both ways, renames, moves across the folder boundary,
a 200-file burst, attachments and a 10-minute outage of the second client all
converged with nothing lost and no re-upload loops. Two saves to the same note in
the same instant can lose one, exactly as plain Sync does with no second client.

The stack can already run a second copy of the sidecar by hand, but three things
are easy to get wrong: pointing it at the whole vault, sharing the first client's
config volume, and syncing `.obsidian` settings that belong to the outer vault.

## What Changes

- New optional service `obsidian-sync-nested`, behind its own Compose profile
  `nested`. Same image, its own config volume, `VAULT_PATH` set to the folder
  (`NESTED_SYNC_SUBPATH`, relative to the vault root), settings sync off.
- New `nested-guard` in the image: when `NESTED_PARENT` is set, the entry point
  and `bootstrap` refuse to run unless `VAULT_PATH` is an existing folder
  strictly inside it. An empty subpath can never point a second client at the
  whole vault.
- `bootstrap` reads three optional variables: `SYNC_DEVICE_NAME` (was hard-coded
  `headless`), `SYNC_CONFIGS` and `SYNC_FILE_TYPES`, applied with
  `ob sync-config` after `sync-setup` when set.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `obsidian-sync-sidecar`: an optional nested sidecar, its path guard, and
  bootstrap settings.

## Impact

- `docker-compose.yml` — one service, one volume, both off unless the `nested`
  profile is selected.
- `obsidian-sync/` — `nested-guard.sh` (new), `entrypoint.sh`, `bootstrap.sh`,
  `Dockerfile`, `README.md`.
- No change for existing deployments: without `NESTED_PARENT` the guard is a
  no-op, and with the new variables unset `bootstrap` behaves as before.
