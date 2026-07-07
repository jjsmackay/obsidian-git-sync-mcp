## Why

The "Named volumes (orchestrators)" section of `README.md` documents mounting
the vault as a Docker named volume (e.g. for a Compose-based orchestrator that
manages volumes itself rather than a host directory) by setting
`VAULT_HOST_PATH` to a bare name. But `docker-compose.yml` never declares a
`vault` entry under its top-level `volumes:` — only `config` and
`oauth_registry` are declared. Compose rejects a bare-name volume reference
that isn't declared (`service "mcp" refers to undefined volume vault: invalid
compose project`), so the documented orchestrator path doesn't actually work
today. This closes that gap.

## What Changes

- Declare a `vault` named volume under `docker-compose.yml`'s top-level
  `volumes:`, alongside the existing `config` and `oauth_registry` volumes.
- Document, next to the existing "Named volumes (orchestrators)" section in
  `README.md`, that `VAULT_HOST_PATH` set to a bare name (no `/`) resolves to
  this declared named volume instead of a host bind mount, and that the
  seeding + chown procedure already documented there still applies.

## Capabilities

### Modified Capabilities

- `container-deployment`: the `mcp` service's vault volume mount gains a
  Compose-managed named-volume option (`VAULT_HOST_PATH` as a bare name),
  in addition to the existing host-bind-mount default.

## Impact

- `docker-compose.yml`: add `vault:` to the top-level `volumes:` block. No
  change to the `mcp`/`obsidian-sync` service definitions themselves — both
  already mount `${VAULT_HOST_PATH:-./vault}:${VAULT_PATH:-/vault}`, which
  already resolves to the named volume once it's declared.
- `README.md`: one clarifying note in the existing orchestrator section.
- No code, env-var, or default-behavior change: `VAULT_HOST_PATH` still
  defaults to `./vault` (a host bind mount), so existing deployments are
  unaffected.
