## 1. README sections

- [x] 1.1 What it is / why — headless, containerised, sync-agnostic; the differentiator vs desktop+REST-API Obsidian MCP servers
- [x] 1.2 Architecture — upstream server + in-process `GitSyncExtension`; `mcp:` writes vs `sync:` sweeps; single git worker; 2-container topology
- [x] 1.3 Quickstart — copy `.env.example` → `.env`, `docker compose up -d`, set `VAULT_GIT_ENABLED=true` (+ a remote) to turn on sync
- [x] 1.4 Configuration — table of the needed upstream `VAULT_*` and every `VAULT_GIT_*` with defaults
- [x] 1.5 Obsidian Sync sidecar — short blurb + link to `obsidian-sync/README.md` (profile `obsidian` + bootstrap)
- [x] 1.6 Exposure — only the MCP port is published; reverse proxy / Cloudflare Tunnel / Tailscale; `VAULT_MCP_ALLOWED_HOSTS` / `VAULT_MCP_PUBLIC_URL`; no tunnel baked in
- [x] 1.7 Monitoring — the three layers (container healthcheck, upstream `VAULT_MCP_HEARTBEAT_URL`, `VAULT_GIT_HEARTBEAT_URL`)
- [x] 1.8 Development — uv, `uv run pytest`; upstream relationship (#57 seam, #62 write listener) + repin-on-merge note; MIT licence

## 2. Accuracy & style

- [x] 2.1 Cross-check the documented `VAULT_GIT_*` set against `grep -rho 'VAULT_GIT_[A-Z_]*' src/ | sort -u` — exact match
- [x] 2.2 Plain, concise, Australian English; no private host/client names; links resolve (`obsidian-sync/README.md`, `.env.example`, LICENSE)

## 3. Validation

- [x] 3.1 `openspec validate docs --strict`
- [x] 3.2 `uv run pytest` still green (sanity; docs change should not affect tests)
