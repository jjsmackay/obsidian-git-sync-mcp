# Proposal

## Why

The entry point decides "bootstrapped" by whether the config dir is non-empty.
`ob login` writes `auth_token` there before `sync-setup` runs. So during a normal
`docker exec -it <container> bootstrap` against an idle sidecar, the poll loop
sees the credential the moment login succeeds, execs `ob sync`, which exits with
"No sync configuration found", and `restart: unless-stopped` restarts the
container. The restart kills the operator's interactive session at the vault
prompt, and the container then crash-loops on the same check until the config
is wiped or set up some other way.

Seen on a fresh deployment: login and MFA succeeded, the session died at
"Remote vault id or name to sync", and the sidecar restarted every few seconds.

## What Changes

- `is_bootstrapped` checks for a configured vault (an entry under
  `$CONFIG_DIR/sync/`, which `sync-setup` creates) instead of any file in the
  config dir.
- The spec says "bootstrapped" means `sync-setup` has run, and adds a scenario
  for the login-only state.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `obsidian-sync-sidecar`: the bootstrapped test, in the idle-poll and dispatch
  requirements.

## Impact

- `obsidian-sync/entrypoint.sh` — one function.
- No change for a sidecar that is already bootstrapped: it has a `sync/` entry
  and starts sync as before. The healthcheck already reads `sync/*/sync.log`, so
  the two now agree on where a configured vault lives.
