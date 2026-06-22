## 1. Dockerfile

- [x] 1.1 `FROM python:3.12-slim`; `apt-get install` `git` + `ca-certificates` (no recommends; clean apt lists); install `uv`
- [x] 1.2 Copy the project and `uv pip install --system .` (resolves upstream `obsidian-web-mcp` from the git branch + `ruamel.yaml`); run as a non-root user
- [x] 1.3 `CMD ["obsidian-git-sync-mcp"]`; expose the MCP port; add the TCP `HEALTHCHECK` (python socket one-liner against `VAULT_MCP_PORT`)

## 2. Compose

- [x] 2.1 `docker-compose.yml`: `mcp` service `build: .`, `env_file: .env`, `restart: unless-stopped`, publish only the MCP port, mount the vault working tree at `VAULT_PATH`
- [x] 2.2 Document (comments) mounting a push credential (read-only deploy key or token remote) — not baked into the image
- [x] 2.3 Mirror the image `HEALTHCHECK` (or rely on the Dockerfile's) so `docker compose ps` shows health

## 3. Config surface

- [x] 3.1 `.env.example`: upstream `VAULT_*` (PATH, MCP_TOKEN, MCP_PORT, MCP_HOST=0.0.0.0, ALLOWED_HOSTS, PUBLIC_URL, OAuth) + ALL `VAULT_GITSYNC_*` with finalised names, extension disabled by default, with a one-line comment per var
- [x] 3.2 `.dockerignore` (exclude `.git`, `.venv`, `__pycache__`, tests, openspec, `.claude`, `HANDOFF.md`)

## 4. Validation

- [x] 4.1 `docker compose config` validates against a populated `.env` (copy `.env.example`)
- [x] 4.2 `docker build` succeeds; `docker run --rm <img> git --version` prints a version; the image's `CMD` is the entry point
- [x] 4.3 Boot check: run the image with no `VAULT_GITSYNC_ENABLED` and a mounted empty vault → server starts and the extension logs loaded-but-DISABLED (no git work). (If a full boot needs more upstream config than is convenient, assert the entry point reaches `serve()` / logs DISABLED and stop the container.)
- [x] 4.4 Cross-check `.env.example` `VAULT_GITSYNC_*` names against `grep -o 'VAULT_GITSYNC_[A-Z_]*' src/` — exact set match
- [x] 4.5 `openspec validate container-deployment --strict`
- [x] 4.6 `uv run pytest` still green (no code regressions)
