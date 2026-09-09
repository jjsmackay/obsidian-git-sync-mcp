## Why

The sidecar `HEALTHCHECK` asserts only that the `ob` config directory is
non-empty — which is permanently true once bootstrapped. It therefore reports on
whether the sidecar was ever set up, never on whether it is currently syncing.

That gap cost three days of silent downtime on a live deployment. At
`2026-09-06T15:19:40Z` the sidecar's `ob` client lost its connection, logged
`Connecting...`, and never reconnected — staying alive, sleeping, holding **zero
socket file descriptors**, with `sync.log` frozen from that moment. Throughout,
every automated signal said the deployment was fine:

- Docker reported the container `healthy`, failing streak 0, because the config
  dir was still non-empty.
- `restart: unless-stopped` never fired, because the process never exited.
- The orchestrator raised no alert, because the stack state stayed `running`.

Meanwhile the local file watcher kept recording changes (`state.db-wal` grew for
three days), so the vault diverged from every device with nothing reporting it.
The outage was found by a human noticing stale notes, not by monitoring.

Bumping the `obsidian-headless` pin to `0.0.14` fixes *that* wedge — upstream's
`0.0.13` entry reads "Fix WebSocket sometimes can get stuck in CONNECTING state
indefinitely." It does not restore the missing signal. Any future hang that
leaves the process alive is still invisible, and a healthcheck that cannot fail
for a running-but-wedged sidecar is worse than none, because it actively asserts
health it never verified.

## What Changes

- A new `obsidian-sync/healthcheck.sh`, installed as `/usr/local/bin/healthcheck`,
  replaces the config-dir test as the sidecar's `HEALTHCHECK` command. It passes
  only when the newest per-vault `sync.log` under the config dir has been written
  within a freshness window, so a wedged-but-alive `ob` goes unhealthy.
- `sync.log` mtime is the signal because continuous sync writes a `Fully synced`
  line every 30s on an exact beat, and stops writing the moment it wedges. This
  was measured on `0.0.14`, not assumed.
- The window is `SYNC_STALE_AFTER` seconds, defaulting to 180 (six missed beats),
  overridable in the same style as the entry point's `SYNC_POLL_INTERVAL`.
- `--start-period` rises from 10s to 120s, so container start and the first log
  write are not mistaken for a wedge.
- The config dir is derived exactly as the entry point derives it
  (`${HOME:-/home/ob}/.config/obsidian-headless`), and the newest `sync.log`
  across all `sync/*/` subdirectories is used, so a multi-vault sidecar is
  judged by its most recently active vault.
- The un-bootstrapped signal is **preserved, not lost**: no config means no
  `sync.log`, which fails the check exactly as the config-dir test did.
- Because the restart policy now has a failing healthcheck to act on for the
  first time, the README documents that Docker does not restart on unhealthy by
  itself, and what an operator must add to get automatic recovery.

No change to sync behaviour, the entry point's run decision, the bootstrap
contract, the vault mount, or the container topology. No new package in the
image — `stat` and `date` are already present.

## Capabilities

### Modified Capabilities

- `obsidian-sync-sidecar`: gains a requirement that the sidecar healthcheck
  asserts current sync liveness rather than mere bootstrap state — the freshness
  signal, the configurable window, the multi-vault rule, and the preserved
  un-bootstrapped behaviour.
- `docs`: the "Exposure and monitoring are documented" requirement fixes the
  monitoring layers at three (container healthcheck, upstream liveness
  heartbeat, git-sync push heartbeat). It widens to four, distinguishing the
  sidecar's sync-freshness healthcheck from the `mcp` service's port
  healthcheck, since the two now assert different kinds of thing.

## Impact

- `obsidian-sync/healthcheck.sh` — new script (the whole behaviour).
- `obsidian-sync/Dockerfile` — install it, replace the `HEALTHCHECK`, raise
  `--start-period`, and correct the comment that documents the old check's
  "bootstrapped?" double duty.
- `obsidian-sync/README.md` — the freshness contract, `SYNC_STALE_AFTER`, the
  30s-beat rationale, and the unhealthy-does-not-restart caveat.
- `README.md` — the monitoring layers list grows the sidecar layer.
- No Python source or test change: the sidecar's container assets are shell and
  Dockerfile, verified by the CI image build and by exercising the script in a
  running container, which is how the existing sidecar scripts are covered.
