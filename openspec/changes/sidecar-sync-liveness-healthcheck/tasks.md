## 1. Healthcheck script

- [ ] 1.1 Add `obsidian-sync/healthcheck.sh` with a header comment stating what it asserts and why mere process liveness is not enough (a wedged `ob` stays alive), using `#!/usr/bin/env bash` and `set -euo pipefail` to match the sibling scripts
- [ ] 1.2 Derive `CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"` exactly as `entrypoint.sh` does, and read `SYNC_STALE_AFTER="${SYNC_STALE_AFTER:-180}"` in the same style as `SYNC_POLL_INTERVAL`
- [ ] 1.3 Select the newest `"$CONFIG_DIR"/sync/*/sync.log` by mtime, tolerating an unmatched glob and unreadable entries without erroring under `set -e`
- [ ] 1.4 Exit non-zero when no `sync.log` exists at all, so an un-bootstrapped sidecar still reports unhealthy exactly as the config-dir test did
- [ ] 1.5 Exit zero when the newest log's age is under the window and non-zero otherwise, printing the age and threshold on failure so `docker inspect`'s health log says why

## 2. Dockerfile

- [ ] 2.1 `COPY --chmod=0755 healthcheck.sh /usr/local/bin/healthcheck`, alongside the existing entry point and bootstrap copies and before the privilege drop
- [ ] 2.2 Replace the `HEALTHCHECK` command with `healthcheck` and raise `--start-period` from 10s to 120s, keeping `--interval=30s --timeout=5s --retries=3`
- [ ] 2.3 Rewrite the comment above the `HEALTHCHECK` so it no longer claims the check doubles as a bootstrapped-only signal: state that it asserts sync freshness, that the un-bootstrapped case still fails via the absent log, and that a wedged-but-running `ob` is the case it exists to catch

## 3. Documentation

- [ ] 3.1 Document the freshness contract in `obsidian-sync/README.md`: the 30s `Fully synced` beat, the 180s default window, `SYNC_STALE_AFTER`, and that the check reads only the log's mtime
- [ ] 3.2 State plainly in `obsidian-sync/README.md` that Docker and Compose do NOT restart a container on unhealthy, so detection is not recovery, and name what an operator must add (orchestrator health-watch, Swarm, or an external supervisor)
- [ ] 3.3 Record the September wedge as the motivating incident in `obsidian-sync/README.md`, including that `restart: unless-stopped` cannot fire for a hung-but-alive process
- [ ] 3.4 Grow the monitoring-layers list in the root `README.md` to four, distinguishing the sidecar's sync-freshness healthcheck from the `mcp` port healthcheck

## 4. Verification

- [ ] 4.1 Build the sidecar image and confirm the healthcheck is present with the new start period (`docker inspect` of the built image)
- [ ] 4.2 Against a running, actively-syncing sidecar, run the script directly and confirm exit 0
- [ ] 4.3 Simulate a wedge WITHOUT breaking sync — copy the log aside, backdate the real file's mtime past the window, confirm exit non-zero and that the message names the age, then restore the mtime and confirm exit 0 again
- [ ] 4.4 Confirm the un-bootstrapped path: run the script with `HOME` pointed at an empty directory and confirm exit non-zero
- [ ] 4.5 Confirm `SYNC_STALE_AFTER` is honoured by passing a deliberately tiny window against a healthy sidecar and seeing it fail
- [ ] 4.6 Confirm the deployed container reports `healthy` after the change and that sync is still `Fully synced`
- [ ] 4.7 Full suite green: `uv run --extra dev python -m pytest`
