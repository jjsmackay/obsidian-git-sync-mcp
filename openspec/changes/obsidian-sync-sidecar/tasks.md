## 1. Sidecar image

- [ ] 1.1 `obsidian-sync/Dockerfile`: a Node slim base; install `obsidian-headless` pinned (e.g. `npm install -g obsidian-headless@0.0.12`). Add `python3`/`make`/`g++` only if `better-sqlite3` has no prebuilt binary for the base (record which was needed)
- [ ] 1.2 Run as non-root; set a stable `HOME` so `ob` writes config to a known path; default the container command to the long-running sync command (discovered from `ob --help`)

## 2. Discover the CLI surface

- [ ] 2.1 Build the image and run `ob --help` (and any `ob <subcommand> --help` needed) to capture the real subcommands (login, sync setup, the run/daemon command) and the actual config dir; use these for the compose command + bootstrap docs

## 3. Compose

- [ ] 3.1 Add the `obsidian-sync` service to `docker-compose.yml` under `profiles: ["obsidian"]`, building `obsidian-sync/`
- [ ] 3.2 Mount the SAME vault working tree as `mcp` (`${VAULT_HOST_PATH}:${VAULT_PATH}`) and a named volume for `ob` config/state at the discovered config dir
- [ ] 3.3 Set the long-running sync command; `restart: unless-stopped`

## 4. Bootstrap docs

- [ ] 4.1 Document the one-time interactive bootstrap via `docker compose run --rm obsidian-sync <ob login / sync-setup commands>` writing into the named volume, then `docker compose --profile obsidian up -d`
- [ ] 4.2 State plainly that login needs a real Obsidian account (operator step, not automated) and note where credentials/state live

## 5. Validation

- [ ] 5.1 `docker build` the sidecar image succeeds; `docker run --rm <img> ob --help` runs headless and prints usage
- [ ] 5.2 `docker compose config` (no profile) → resolved services do NOT include `obsidian-sync`; `docker compose --profile obsidian config` → includes both `mcp` and `obsidian-sync`
- [ ] 5.3 Confirm the persisted-volume mount path matches the real `ob` config dir and the vault mount matches `mcp`
- [ ] 5.4 `openspec validate obsidian-sync-sidecar --strict`; `uv run pytest` still green
