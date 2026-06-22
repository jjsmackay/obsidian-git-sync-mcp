## Why

The extension is a Python package with no way to run it as a service. This change
makes it deployable: a container image that runs the upstream MCP server with our
git-sync extension loaded, and a Compose stack to operate it. It also finalises
the `VAULT_GITSYNC_*` env-var names (until now provisional) in a single
`.env.example`.

## What Changes

- Add a `Dockerfile`: `FROM python:3.12-slim`, install `git` + CA certs (the
  worker shells out to `git`, and the build resolves the upstream git
  dependency), install this package with uv (`uv pip install --system .`, pulling
  upstream `obsidian-web-mcp` and `ruamel.yaml`), and set `CMD` to our console
  entry point `obsidian-git-sync-mcp` (which runs `serve([GitSyncExtension()])`).
  Upstream publishes no image, so we build from the Python base rather than
  `FROM` an upstream image.
- Add a `docker-compose.yml` with the always-on `mcp` service: builds the image,
  reads `.env`, mounts the vault git working tree as a volume, publishes only the
  MCP port, sets a `restart` policy and a `HEALTHCHECK`. (The optional
  `obsidian-sync` sidecar under a Compose profile is the next change.)
- `HEALTHCHECK`: a dependency-free TCP check that the MCP port is accepting
  connections (upstream serves no usable inbound health route — `/health` is
  reserved/auth-exempt with no handler). The monitoring change adds the outbound
  push heartbeat.
- Add `.env.example` documenting the full runtime surface — the upstream
  `VAULT_*` vars and **all** `VAULT_GITSYNC_*` vars with their finalised names —
  and a `.dockerignore`.

## Capabilities

### New Capabilities
- `container-deployment`: the image definition, the Compose `mcp` service, the
  HEALTHCHECK, and the `.env.example` contract that pins the configuration
  surface.

### Modified Capabilities
<!-- None. This packages existing behaviour for deployment; no code requirements
     change. The env-var names it documents are the ones the code already reads. -->

## Impact

- New files: `Dockerfile`, `docker-compose.yml`, `.env.example`, `.dockerignore`.
- Finalises the `VAULT_GITSYNC_*` names (resolves the HANDOFF "provisional names"
  flag): `ENABLED`, `SWEEP_INTERVAL`, `REMOTE`, `BRANCH`, `PUSH_DEBOUNCE`,
  `PUSH_MAX_INTERVAL`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `STAMP`.
- Operational surface: the vault must be a git working tree on a persisted
  volume; pushing needs a credential (deploy key or token-bearing remote),
  mounted not baked. Exposure (reverse proxy / Cloudflare Tunnel / Tailscale) is
  documented, not built in — only the MCP port is published.
