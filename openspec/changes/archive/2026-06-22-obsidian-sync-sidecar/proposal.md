## Why

git sync mirrors the vault to a remote, but the project's premise is that
**Obsidian Sync** keeps human devices (phone, desktop) in step while the
headless host serves MCP and commits to git. That needs the official
`obsidian-headless` CLI (`ob`) running headless beside the MCP container. This is
the HANDOFF's biggest standalone risk — getting `ob` to build and run in a slim
container — so it is its own change and validated early.

## What Changes

- Add a sidecar image (`obsidian-sync/Dockerfile`) on a Node base that installs
  `obsidian-headless` (npm; bin `ob`; native dep `better-sqlite3`) and can run
  `ob` headless.
- Add an `obsidian-sync` service to `docker-compose.yml` under a Compose
  **profile** `obsidian`, so it is **opt-in** — `docker compose up` runs only the
  `mcp` service; `docker compose --profile obsidian up` adds the sidecar.
- Persist `ob`'s state on a named volume (the credentials + `state.db` live under
  `~/.config/obsidian-headless/`), and share the same vault working tree the
  `mcp` service mounts, so device edits land on disk for the git-sync worker's
  sweep to pick up.
- Document the one-time interactive bootstrap (`ob login`, `ob sync-setup`) via
  `docker compose run`, derived from the CLI's actual subcommands, and the
  long-running sync command the service uses.
- Validate that the image builds and `ob` runs in the slim container (the risk);
  real Obsidian Sync login is an operator step (needs an account) and is
  documented, not automated.

## Capabilities

### New Capabilities
- `obsidian-sync-sidecar`: the `ob` sidecar image, the profile-gated
  `obsidian-sync` Compose service, the persisted config volume, the shared vault
  mount, and the bootstrap procedure.

### Modified Capabilities
<!-- None. This adds an optional service alongside the existing mcp service;
     the container-deployment requirements are unchanged. -->

## Impact

- New files: `obsidian-sync/Dockerfile` (and any small entrypoint/helper); a new
  service + named volume in `docker-compose.yml`; bootstrap docs.
- New env/volumes: a named volume for `ob` config/state; the shared vault volume.
- Risk surface: `better-sqlite3` is a native module — the image must provide what
  it needs (prebuilt binary or build toolchain). The `mcp` service is unaffected
  whether or not the profile is active.
- v1 ships only the coarse `mcp:`/`sync:` provenance; reading `ob`'s `state.db`
  for `user@device` attribution remains a v2 item, untouched here.
