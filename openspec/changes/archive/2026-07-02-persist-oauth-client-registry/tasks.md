## 1. Image: pre-create the registry mount point

- [x] 1.1 In `Dockerfile`, after the `useradd --uid 10001 appuser` line and
  before `USER appuser`, create `/data` owned by uid 10001 (e.g.
  `RUN install -d -o 10001 -g 10001 /data`) so a fresh root-owned named volume
  inherits writable ownership on first mount
- [x] 1.2 Add a short comment explaining why (uid-10001 write of the 0600 OAuth
  registry fails silently on a root-owned volume; mirrors the sidecar config-dir
  fix)

## 2. Compose: dedicated volume + OAUTH_CLIENTS_PATH

- [x] 2.1 In `docker-compose.yml`, add a named volume (`oauth_registry`) under
  the top-level `volumes:` block
- [x] 2.2 Mount that volume on the `mcp` service at `/data`
- [x] 2.3 Set `OAUTH_CLIENTS_PATH=/data/oauth_clients.json` in the `mcp` service
  environment
- [x] 2.4 Add a comment noting the registry MUST stay off the vault tree (the
  worker commits and pushes `/vault`; the registry holds per-client secrets)

## 3. Docs

- [x] 3.1 Document `OAUTH_CLIENTS_PATH` in `.env.example` — its purpose, the
  ephemeral upstream default, and that the compose deployment points it at the
  `/data` volume so registered clients survive a redeploy

## 4. Verify

- [x] 4.1 Compose resolves the `/data` mount + `oauth_registry` volume +
  `OAUTH_CLIENTS_PATH` on the `mcp` service, with the registry NOT under
  `/vault`. (Docker unavailable on this host; verified by structural YAML parse
  instead of `docker compose config`. Full `docker compose config` runs in CI.)
- [x] 4.2 `/data` is created owned by uid 10001 in the image via
  `install -d -o 10001 -g 10001 /data`. (Docker unavailable on this host; the
  actual image build + ownership runs in CI `build-containers.yml` on push —
  `install -d -o -g` deterministically sets ownership.)
- [x] 4.3 `openspec validate persist-oauth-client-registry --strict` passes
- [x] 4.4 Test suite green (`uv run --extra dev python -m pytest`): 124 passed,
  unchanged — config/image-only change touches no Python
