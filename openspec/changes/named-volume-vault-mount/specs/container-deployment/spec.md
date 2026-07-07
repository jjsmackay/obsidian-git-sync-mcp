## ADDED Requirements

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
