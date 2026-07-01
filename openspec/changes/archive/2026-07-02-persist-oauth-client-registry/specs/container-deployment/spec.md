## ADDED Requirements

### Requirement: OAuth client registry persists on a dedicated volume

The mcp service SHALL persist the upstream server's dynamically-registered OAuth
client registry on a dedicated named volume that is separate from the vault
working tree, so registered MCP clients survive a redeploy instead of being
rejected with `invalid_client`. `docker-compose.yml` SHALL define a named volume
mounted on the `mcp` service at `/data` and SHALL set `OAUTH_CLIENTS_PATH` to a
path on that volume (`/data/oauth_clients.json`). The registry SHALL NOT be
placed under the vault path: the git-sync worker sweeps, commits and pushes the
vault tree, and the registry holds per-client secrets, so a location inside the
tree would publish those secrets to the vault's git remote.

#### Scenario: Registry survives a redeploy

- **WHEN** an MCP client has registered via dynamic client registration and the
  mcp service is redeployed
- **THEN** the registry file persists on the dedicated volume and the client's
  `client_id` is still recognised, so it is not rejected with `invalid_client`

#### Scenario: Registry volume is separate from the vault

- **WHEN** the `mcp` service volume mounts and `OAUTH_CLIENTS_PATH` are inspected
- **THEN** the registry path resolves onto a dedicated named volume mounted at
  `/data`, not onto the vault working tree the git-sync worker commits and pushes

### Requirement: OAuth registry volume inherits writable ownership from the image

The mcp image SHALL pre-create the `/data` directory owned by uid 10001 before
the dedicated registry volume is mounted there, so a fresh (root-owned) named
volume inherits container-user ownership on first use and the non-root server can
write the registry without a host-side chown. This mirrors the sidecar's
image-side ownership fix for its config volume; without it the registry save
(`os.open(..., 0o600)` as uid 10001) fails silently and nothing persists.

#### Scenario: Fresh registry volume is writable by the server user

- **WHEN** the mcp service first starts with a fresh named volume mounted at
  `/data`
- **THEN** `/data` is owned by uid 10001 and the server writes
  `oauth_clients.json` (mode 0600) without a host-side chown

#### Scenario: Silent-failure mode is avoided

- **WHEN** the image build is inspected for the `/data` mount point
- **THEN** the directory is created and chowned to uid 10001 in the image, so a
  root-owned fresh volume does not leave the registry save failing silently
