## Why

Everything works but the README is a 10-line stub. A self-hostable,
open-source-quality project needs docs an operator can actually deploy from: what
it is and how it differs, the architecture in brief, a Docker quickstart, the
full configuration surface, the optional Obsidian Sync sidecar bootstrap, how to
expose it safely, and how to monitor it. This change writes them.

## What Changes

- Expand `README.md` into the operator/contributor entry point:
  - **What it is / why** — headless, containerised, sync-agnostic; how it differs
    from desktop-plus-REST-API Obsidian MCP servers.
  - **Architecture** — the upstream server + in-process `GitSyncExtension`; the
    classified event stream (`mcp:` writes vs `sync:` sweeps) and the single git
    worker; the 2-container topology.
  - **Quickstart** — `.env` from `.env.example`, `docker compose up -d`, enabling
    git sync.
  - **Configuration** — a table of the upstream `VAULT_*` vars the deployment
    needs and every `VAULT_GITSYNC_*` var, defaults included.
  - **Obsidian Sync sidecar** — link to `obsidian-sync/README.md` for the
    profile + bootstrap.
  - **Exposure** — only the MCP port is published; document reverse proxy /
    Cloudflare Tunnel / Tailscale and the `VAULT_MCP_ALLOWED_HOSTS` /
    `VAULT_MCP_PUBLIC_URL` requirements. No tunnel baked in.
  - **Monitoring** — the three layers (container healthcheck, upstream liveness
    heartbeat, git-sync push heartbeat).
  - **Development** — uv, `uv run pytest`; the upstream relationship (#57 seam,
    #62 write listener) and the repin-on-merge note.
- Keep the upstream-relationship and licence framing accurate (consume upstream,
  contribute changes there; MIT).

## Capabilities

### New Capabilities
- `docs`: the README contract — the sections an operator/contributor needs and
  the accuracy guarantees (config table matches the code; quickstart matches the
  compose stack).

### Modified Capabilities
<!-- None. Documentation only; no code or behaviour changes. -->

## Impact

- Changed file: `README.md` (and small cross-links to `obsidian-sync/README.md`
  and `.env.example`).
- No code, no dependencies, no behaviour change.
- Public-facing copy: plain and concise; no private host/client names.
