## Context

The sidecar runs one long-lived process, `ob sync --path /vault --continuous`,
as PID 1. The failure mode this change addresses is not a crash — it is that
process staying alive while doing no useful work. Any signal derived from process
existence is therefore useless by construction, which is what made the September
outage invisible: PID 1 was `S` (sleeping), the container was `healthy`, and the
restart policy had nothing to act on.

So the design question is narrow: what observable, inside the container, changes
when sync stops working but the process does not die?

## Goals / Non-Goals

Goals:

- Fail the healthcheck within minutes of sync going silent, whatever the cause.
- Keep the existing "un-bootstrapped reports unhealthy" behaviour.
- Add no package to the image and no dependency on network reachability.

Non-Goals:

- Automatic recovery. A failing healthcheck does not restart a container in
  plain Docker or Compose; that needs Swarm, an external supervisor, or an
  orchestrator watching health. This change makes the condition *detectable* and
  documents the gap. Restarting on it is an operator decision, deliberately not
  baked in.
- Alerting. That belongs to whatever watches container health, plus the existing
  push-heartbeat layer in `monitoring`.
- Distinguishing *why* sync stopped (network, auth, upstream bug). The
  healthcheck answers "is sync alive", not "what broke".

## Decisions

### Signal: freshness of the newest per-vault `sync.log`

`ob` writes `sync.log` under
`${HOME:-/home/ob}/.config/obsidian-headless/sync/<vault-id>/`, and in
continuous mode it appends a `Fully synced` line every 30s. Measured on `0.0.14`
in a live steady state, the beat is exact — `…10:59:52, 11:00:22, 11:00:52,
11:01:22, …` — with extra lines interleaved when files actually move. When the
client wedged, the file's last write was the `Connecting...` line and the mtime
then sat unchanged for three days. The signal is present exactly when sync works
and absent exactly when it does not.

The check takes the newest `sync.log` across all `sync/*/` subdirectories rather
than assuming one vault, so a sidecar configured for several vaults is judged by
its most recently active one. This is deliberately lenient: it answers "is this
sidecar syncing anything", not "is every configured vault current".

### Rejected alternatives

- **Config-dir non-empty (status quo).** Permanently true once bootstrapped.
  This is the bug.
- **Process liveness / a `pgrep ob`.** True throughout the outage.
- **`ob sync-status`.** Verified against `0.0.14`: prints static configuration
  only — vault, mode, conflict strategy, file types — with no connection state
  and no last-sync timestamp. It would have printed the same output happily
  throughout the three-day outage.
- **`state.db-wal` mtime.** Actively misleading, and worth recording because it
  is the obvious-looking choice. The WAL kept being written *during* the outage
  (it grew to 4.1 MB) because the local file watcher was still recording
  changes; only the shipping of them had stopped. A healthcheck on the WAL would
  have reported healthy for all three days.
- **An outbound probe (TLS to the sync endpoint).** Tests the network, not the
  client. Egress was provably fine during the outage — DNS and TLS from inside
  the container both succeeded while sync was dead — so this would also have
  passed.

### Window: 180s default, overridable

Six missed 30s beats. Long enough that a slow beat or a busy sweep cannot flap
the check, short enough that detection is minutes rather than days. Exposed as
`SYNC_STALE_AFTER`, matching the entry point's existing `SYNC_POLL_INTERVAL`
convention, so an operator on a slow link can widen it without rebuilding.

With `--interval=30s --retries=3`, an unhealthy verdict lands roughly 180-270s
after the last log write.

### Start period: 10s to 120s

A fresh container must boot, decide its run mode, and get far enough into a sync
session to write a line. On a cold start with a real backlog the log is written
continuously during upload, so 120s is ample; it only has to cover start-up
itself. Failures during the start period do not count toward the retry budget,
so a generous value costs nothing but delayed detection on a genuinely
dead-on-arrival container.

## Risks / Trade-offs

- **Log format dependency.** The check depends on `ob` continuing to write
  `sync.log` periodically in continuous mode. It does not parse the file — only
  its mtime — so wording changes are harmless, but a future version that stops
  writing periodically, or adds log rotation that recreates the file elsewhere,
  would break it. Accepted because the alternatives above are all strictly
  worse, and the failure direction is a false *unhealthy* (loud) rather than a
  false healthy (silent), which is the right way round for this bug.
- **Ephemeral and passthrough containers report unhealthy.** A
  `docker compose run --rm obsidian-sync bootstrap`, or a passthrough `sh` for
  debugging, runs no sync session and so fails the check once past the start
  period. Previously such a container reported healthy. This is a cosmetic
  regression on short-lived containers and is preferred to weakening the signal
  on the long-lived one.
- **`sync.log` growth is unbounded.** Observed at 13.9 MB after two months. Not
  introduced by this change and not addressed here, but noted because the
  healthcheck now depends on that file.
