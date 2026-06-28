## 1. Entry point: poll-and-auto-start

- [ ] 1.1 Add a `SYNC_POLL_INTERVAL="${SYNC_POLL_INTERVAL:-5}"` default alongside `VAULT_PATH`/`CONFIG_DIR` at the top of `obsidian-sync/entrypoint.sh`.
- [ ] 1.2 Replace the terminal idle branch: print the existing bootstrap instructions once, then `while ! is_bootstrapped; do sleep "$SYNC_POLL_INTERVAL"; done`, then `exec ob sync --path "$VAULT_PATH" --continuous` (the same command the already-bootstrapped branch uses).
- [ ] 1.3 Confirm the three existing branches (explicit `bootstrap`/`BOOTSTRAP`, explicit passthrough command, already-bootstrapped → sync) are untouched, and `set -euo pipefail` still holds (the `is_bootstrapped` call sits in a `while` condition so its non-zero exit does not trip `errexit`).

## 2. Docs

- [ ] 2.1 Update `obsidian-sync/README.md`: drop the "restart after bootstrapping a running container" caveat and describe the idle entry point auto-starting sync once config appears; note `SYNC_POLL_INTERVAL` (default 5s) as the override.

## 3. Verify

- [ ] 3.1 `bash -n obsidian-sync/entrypoint.sh` — syntax clean.
- [ ] 3.2 `uv run --extra dev python -m pytest` — confirm nothing else broke (bare `pytest` / `uv run pytest` fail; use the dev extra + `python -m`). If `uv`/deps are unavailable in the worktree, report that.
