# Proposal

## Why

Three of the four monitoring layers this project documents are unreachable in
practice. The sidecar's sync-freshness verdict exists only as Docker container
health, which nothing outside the daemon reads; the git-sync push heartbeat
fires on a cadence no fixed-interval push monitor can be configured against; and
neither the README nor `.env.example` gives an operator the wiring to point a
push-style monitor at the deployment. The result is a stack that computes
correct health verdicts every 30 seconds and tells nobody — which is how the
three-day wedged-sync outage that motivated the sidecar healthcheck went
unnoticed in the first place.

This closes the gap without adding recovery. Automatic restart-on-stall is
deliberately out of scope (see below): detection that reaches a human is the
prerequisite, and a watchdog that acts on an unproven signal is worse than none.

**Depends on `surface-stage-failures`, which must land first.** The git-sync beat
is gated on the worker not being degraded, and that state does not exist until
that change adds it. Landing this one alone would ship a beat that keeps firing
through a silent staging failure — the precise outage that motivated both
changes.

## What Changes

- **BREAKING** (behavioural, opt-in only): the git-sync push heartbeat changes
  meaning from "a push just succeeded" to "the worker completed a push cycle
  cleanly, owing nothing to the remote". It now also fires when there was nothing
  to push, is suppressed while the worker is degraded, and is rate-limited.
  Silence therefore means the worker is dead, cannot stage or commit, *or* has
  commits stuck unpushed — a signal a fixed-interval push monitor can actually
  consume. Deployments with no heartbeat URL configured are unaffected.
- New `VAULT_GIT_HEARTBEAT_INTERVAL` (default 60s) putting a floor on beat
  frequency, mirroring the upstream server's own heartbeat variable naming.
  Validated fail-closed alongside the existing heartbeat URL check.
- New `SYNC_HEARTBEAT_URL` for the `obsidian-sync` sidecar: an outbound beat
  fired only when the existing sync-freshness check passes, so a wedged `ob`
  goes silent and a push monitor alerts. Disabled when unset.
- The sidecar's `HEALTHCHECK` gains a thin reporting wrapper so the beat rides
  Docker's existing 30s clock rather than adding a process, while
  `healthcheck` itself stays a pure, side-effect-free diagnostic an operator can
  run by hand.
- Documentation of all three beats — including the upstream server's
  `VAULT_MCP_HEARTBEAT_URL`, which already works and only lacked an entry in
  `.env.example` — so wiring a monitor is a documented operator step rather than
  a code read.

Explicitly **not** in scope: restarting a stalled sidecar. The predecessor
deployment paired its heartbeat with a watchdog that bounced the sync service on
a stale log, with a cooldown to prevent restart loops. That is a separate change,
deferred until these beats have run long enough to show the freshness window
does not flap.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `monitoring`: the push-heartbeat trigger changes from "after a successful
  push" to "after a push cycle that leaves nothing owed to the remote", gains a
  minimum-interval floor, and the new interval variable joins the fail-closed
  validation.
- `obsidian-sync-sidecar`: a new optional outbound heartbeat gated on the
  sync-freshness verdict, carried by a reporting wrapper around the existing
  healthcheck, with the same ping discipline the git-sync heartbeat follows.
- `docs`: the monitoring layers become five rather than four, and the
  configuration surface documented for operators grows by the new variables.

## Impact

- `src/obsidian_git_sync/worker.py` — beat trigger moves from the push-success
  branch to the end of the push cycle, with a rate-limit gate.
- `src/obsidian_git_sync/config.py` — new interval variable, accessor, and
  fail-closed validation.
- `obsidian-sync/` — new reporting wrapper script, `HEALTHCHECK` command change
  in the sidecar `Dockerfile`, sidecar README. `healthcheck.sh` is unchanged.
- `docker-compose.yml` — heartbeat variable passed through to the sidecar
  service.
- `.env.example`, `README.md` — new variables and the fifth monitoring layer.
- `tests/` — worker beat-trigger cases and interval validation.
- No new runtime dependency: the sidecar image has neither `curl` nor `wget`, so
  its ping uses the `node` binary the image already ships, the same way the mcp
  image's healthcheck uses its `python`.
- Both heartbeats stay disabled by default and fail soft, so a deployment that
  configures neither behaves exactly as today.
