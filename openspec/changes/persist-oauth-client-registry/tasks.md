## 1. Image: pre-create the registry mount point

- [ ] 1.1 In `Dockerfile`, after the `useradd --uid 10001 appuser` line and
  before `USER appuser`, create `/data` owned by uid 10001 (e.g.
  `RUN install -d -o 10001 -g 10001 /data`) so a fresh root-owned named volume
  inherits writable ownership on first mount
- [ ] 1.2 Add a short comment explaining why (uid-10001 write of the 0600 OAuth
  registry fails silently on a root-owned volume; mirrors the sidecar config-dir
  fix)

## 2. Compose: dedicated volume + OAUTH_CLIENTS_PATH

- [ ] 2.1 In `docker-compose.yml`, add a named volume (e.g. `mcp_oauth`) under
  the top-level `volumes:` block
- [ ] 2.2 Mount that volume on the `mcp` service at `/data`
- [ ] 2.3 Set `OAUTH_CLIENTS_PATH=/data/oauth_clients.json` in the `mcp` service
  environment
- [ ] 2.4 Add a comment noting the registry MUST stay off the vault tree (the
  worker commits and pushes `/vault`; the registry holds per-client secrets)

## 3. Docs

- [ ] 3.1 Document `OAUTH_CLIENTS_PATH` in `.env.example` — its purpose, the
  ephemeral upstream default, and that the compose deployment points it at the
  `/data` volume so registered clients survive a redeploy

## 4. Verify

- [ ] 4.1 `docker compose config` validates and resolves the `/data` mount +
  volume on the `mcp` service
- [ ] 4.2 Build the image and confirm `/data` is owned by uid 10001
  (`docker run --rm <img> stat -c '%u' /data` → `10001`)
- [ ] 4.3 `openspec validate persist-oauth-client-registry --strict` passes
- [ ] 4.4 Run the test suite (`uv run --extra dev python -m pytest`) — expect no
  change, since this is a config/image-only change
