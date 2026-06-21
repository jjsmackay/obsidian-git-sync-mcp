## 1. README sections

- [ ] 1.1 What it is / why — headless, containerised, sync-agnostic; the differentiator vs desktop+REST-API Obsidian MCP servers
- [ ] 1.2 Architecture — upstream server + in-process `GitSyncExtension`; `mcp:` writes vs `sync:` sweeps; single git worker; 2-container topology
- [ ] 1.3 Quickstart — copy `.env.example` → `.env`, `docker compose up -d`, set `VAULT_GITSYNC_ENABLED=true` (+ a remote) to turn on sync
- [ ] 1.4 Configuration — table of the needed upstream `VAULT_*` and every `VAULT_GITSYNC_*` with defaults
- [ ] 1.5 Obsidian Sync sidecar — short blurb + link to `obsidian-sync/README.md` (profile `obsidian` + bootstrap)
- [ ] 1.6 Exposure — only the MCP port is published; reverse proxy / Cloudflare Tunnel / Tailscale; `VAULT_MCP_ALLOWED_HOSTS` / `VAULT_MCP_PUBLIC_URL`; no tunnel baked in
- [ ] 1.7 Monitoring — the three layers (container healthcheck, upstream `VAULT_MCP_HEARTBEAT_URL`, `VAULT_GITSYNC_HEARTBEAT_URL`)
- [ ] 1.8 Development — uv, `uv run pytest`; upstream relationship (#57 seam, #62 write listener) + repin-on-merge note; MIT licence

## 2. Accuracy & style

- [ ] 2.1 Cross-check the documented `VAULT_GITSYNC_*` set against `grep -rho 'VAULT_GITSYNC_[A-Z_]*' src/ | sort -u` — exact match
- [ ] 2.2 Plain, concise, Australian English; no private host/client names; links resolve (`obsidian-sync/README.md`, `.env.example`, LICENSE)

## 3. Validation

- [ ] 3.1 `openspec validate docs --strict`
- [ ] 3.2 `uv run pytest` still green (sanity; docs change should not affect tests)
