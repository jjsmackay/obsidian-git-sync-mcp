## Why

The upstream server persists its dynamically-registered OAuth client registry
(the DCR `client_id` → secret map) to `OAUTH_CLIENTS_PATH`, which defaults to a
path under the container user's home. That path is on the container's ephemeral
layer, not on any named volume, so every redeploy wipes it. Already-connected
MCP clients then replay a `client_id` the restarted server no longer knows and
are rejected with `invalid_client`, forcing a manual re-registration after each
deploy. It is the only out-of-volume, non-derived state the mcp container keeps
(the frontmatter index is an in-memory cache rebuilt at boot; everything else
lives on the vault volume).

## What Changes

- Add a dedicated named volume for the mcp service, mounted at `/data`, that
  holds the OAuth client registry — a single-purpose volume separate from the
  vault working tree.
- Point `OAUTH_CLIENTS_PATH` at `/data/oauth_clients.json` in the mcp service
  configuration so the registry lands on that volume.
- The mcp image SHALL pre-create `/data` owned by uid 10001 before the volume is
  mounted, so a fresh (root-owned) named volume inherits writable ownership on
  first use — the same image-side ownership fix the sidecar already applies to
  its `config` volume. Without it the registry save (`os.open(..., 0o600)`)
  fails silently as the non-root user and nothing persists.
- The registry MUST NOT live under `/vault`: the git-sync worker sweeps, commits
  and pushes the vault tree, and the registry file holds per-client secrets — a
  path inside the tree would publish those secrets to the vault's git remote.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `container-deployment`: adds a requirement for a dedicated, ownership-correct
  named volume that persists the OAuth client registry off the vault tree, and
  requires the mcp service to point `OAUTH_CLIENTS_PATH` at it.

## Impact

- `Dockerfile` (mcp image): pre-create `/data` as uid 10001.
- `docker-compose.yml`: new named volume mounted at `/data` on the `mcp`
  service; `OAUTH_CLIENTS_PATH=/data/oauth_clients.json`.
- `.env.example`: document `OAUTH_CLIENTS_PATH` and its default-vs-persisted
  behaviour.
- No Python code change — `OAUTH_CLIENTS_PATH` and the 0600 registry writer are
  upstream behaviour this change only configures.
- Deployment (`sybsidian` stack): add the volume + env before the next redeploy;
  first authenticate after the change re-registers a client that then survives.
