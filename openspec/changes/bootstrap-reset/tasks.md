## 1. Bootstrap: --reset flag

- [x] 1.1 Add `CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"` alongside `VAULT_PATH` at the top of `obsidian-sync/bootstrap.sh` (identical expression to `entrypoint.sh:24`).
- [x] 1.2 Parse args: no args → normal bootstrap; `--reset` → set a reset flag and continue; anything else → print `usage: bootstrap [--reset]` to stderr and `exit 2`.
- [x] 1.3 On `--reset`, before deleting anything: `read -rp` for an explicit `yes`; any other answer prints an abort message and exits 0 (no harm done).
- [x] 1.4 On confirmation, guard the path (`CONFIG_DIR` non-empty, `!= /`, is a directory) then remove its *contents* safely (subshell with `nullglob`/`dotglob` globbing under `"$CONFIG_DIR"`, or `find "$CONFIG_DIR" -mindepth 1 -delete`) — never `rm -rf` an unquoted/bare path, never the mount point itself.
- [x] 1.5 Fall through to the unchanged `ob login` → `sync-list-remote` → `sync-setup` (hidden e2e password via `read -rs`) → `sync-status` flow; keep `set -euo pipefail` correct (confirmation read and wipe must not trip `errexit`).

## 2. Entry point: forward --reset (clean only)

- [x] 2.1 In `obsidian-sync/entrypoint.sh`, change the explicit-`bootstrap`-arg branch to `shift` and `exec bootstrap "$@"` so a forwarded `--reset` reaches `bootstrap`; keep the `BOOTSTRAP` env branch's no-arg `exec bootstrap`. Leave the passthrough, already-bootstrapped, and poll-loop branches untouched.

## 3. Docs

- [x] 3.1 Update `obsidian-sync/README.md`: replace the manual stop/`alpine rm -rf`/one-off-run re-bootstrap recipe with `docker exec -it <c> bootstrap --reset`; note that it confirms first and then runs the normal login flow.

## 4. Verify

- [x] 4.1 `bash -n obsidian-sync/bootstrap.sh` and `bash -n obsidian-sync/entrypoint.sh` — syntax clean.
- [x] 4.2 `uv run --extra dev python -m pytest` — confirm nothing else broke (bare `pytest` / `uv run pytest` fail; use the dev extra + `python -m`).
