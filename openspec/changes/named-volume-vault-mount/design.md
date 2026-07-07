## Context

`docker-compose.yml`'s `mcp` and `obsidian-sync` services both mount the vault
at `${VAULT_HOST_PATH:-./vault}:${VAULT_PATH:-/vault}`. Compose resolves a bind
source containing `/` (or starting `.`) as a host path, and a bare name as a
reference to a named volume declared in the file's top-level `volumes:` block
— but only `config` and `oauth_registry` are declared there today. Setting
`VAULT_HOST_PATH` to a bare name (as README's orchestrator section already
describes) currently fails Compose validation.

## Goals / Non-Goals

**Goals:**
- Make the documented named-volume path actually work: declaring `vault:` so
  `VAULT_HOST_PATH=<bare-name>` resolves to a Compose-managed volume.

**Non-Goals:**
- No change to the seeding/chown procedure (`openspec/specs/container-deployment`
  "Named vault volume must be seeded and chowned" already covers it and stays
  as-is).
- No change to the default (host bind-mount) path or its default value
  (`./vault`).

## Decisions

- Add exactly one top-level volume, named `vault`, matching the naming used
  for `config`/`oauth_registry`. No other compose changes are needed: the
  existing `${VAULT_HOST_PATH:-./vault}:${VAULT_PATH:-/vault}` mount syntax on
  both services already works for either a host path or a declared named
  volume — the only missing piece was the declaration itself.
- Considered a second, separate compose file (`docker-compose.orchestrator.yml`)
  for named-volume deployments instead. Rejected: the existing var-driven mount
  already supports both cases once the volume is declared, so a second file
  would just duplicate the whole stack definition for no behavioural gain.

## Risks / Trade-offs

- [Declaring `vault:` unconditionally means `docker compose down -v` on a
  bind-mount deployment now also lists a `vault` volume in that command's
  scope] → Compose only creates/removes a named volume if it's actually used
  as a mount source; a deployment using the default host-path
  `VAULT_HOST_PATH` never creates the `vault` volume, so `down -v` has nothing
  to remove there. No behavioural change for existing deployments.
