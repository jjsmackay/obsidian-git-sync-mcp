## Why

An operator running this unattended needs to know sync is actually working — not
just that the server process is up. The container `HEALTHCHECK` (deployment
change) covers "is it listening" and the upstream `VAULT_MCP_HEARTBEAT_URL`
covers "is the server alive", but neither tells you the git mirror is keeping up.
The bobsidian origin pinged a monitor after each successful sync; this change
ports that as a git-sync push heartbeat.

## What Changes

- Add a `monitoring` capability: an optional push heartbeat that pings a
  configurable URL **after a successful push**, signalling that git sync reached
  the remote. Compatible with any push-style monitor (Uptime Kuma,
  Healthchecks.io, Cronitor, …).
- Port the upstream heartbeat ping discipline: a single GET, **no redirects
  followed**, read at most a small cap of the body, a short timeout, and logging
  that never echoes the URL (it can be a capability URL with a secret in the
  path) — only the host and exception type.
- Wire it into the worker: on a successful push in the push cycle, fire the
  heartbeat (fail-soft — a heartbeat failure never affects sync). It does not
  fire on a failed push or in commit-only mode (no remote → no push → the
  container healthcheck is the liveness signal there).
- Gate it behind `VAULT_GIT_HEARTBEAT_URL` (empty = disabled), validated
  http(s) at startup (fail-closed) like the upstream heartbeat.
- Document the full monitoring story: container `HEALTHCHECK` (liveness) +
  upstream `VAULT_MCP_HEARTBEAT_URL` (server liveness) + this push heartbeat
  (sync health). `register_routes` intentionally stays unused — `/health` is
  upstream-reserved and a bespoke status route is not worth the auth-exempt
  footgun for v1.

## Capabilities

### New Capabilities
- `monitoring`: the push-heartbeat config + validation, the ping helper (ported
  discipline), and its fire-on-successful-push integration in the worker.

### Modified Capabilities
<!-- None. The heartbeat fires from the worker's existing push cycle as additive
     behaviour; the git-worker requirements are unchanged. -->

## Impact

- New code: `heartbeat.py` (the ping helper); a call from the worker's push
  success path; config + validation for `VAULT_GIT_HEARTBEAT_URL`.
- New `VAULT_GIT_*` config: `HEARTBEAT_URL` (added to `.env.example`).
- No new third-party dependency (stdlib `urllib`, as upstream uses).
