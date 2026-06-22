## Context

Three layers answer different questions: the container `HEALTHCHECK` (deployment
change) answers "is the port listening"; the upstream `VAULT_MCP_HEARTBEAT_URL`
answers "is the server process alive" (a daemon thread GETs a monitor on an
interval); neither answers "is the git mirror keeping up". The bobsidian origin's
`heartbeat.sh` pinged a monitor after each successful sync — this change ports
that as the sync-health signal.

## Goals / Non-Goals

**Goals:**

- An optional push heartbeat fired after a successful push, for any push-style
  monitor.
- The same hardened ping discipline upstream uses (no redirects, bounded read,
  short timeout, secret-safe logging).
- Fail-closed config validation; fail-soft runtime.

**Non-Goals:**

- No new heartbeat *loop* — the upstream server already owns periodic
  server-liveness pings via `VAULT_MCP_HEARTBEAT_URL`. Ours is event-driven
  (on push success), not a timer.
- No `/gitsync/status` HTTP route. `/health` is upstream-reserved and a bespoke
  bearer-protected status route is not worth the auth-exempt footgun for v1;
  `register_routes` stays a no-op.
- No new dependency — stdlib `urllib`, as upstream.

## Decisions

**Event-driven on push success, not a timer.** The question this heartbeat
answers is "did sync reach the remote recently", which is exactly "did a push
just succeed". Firing it from the worker's push success path means a stalled or
failing sync stops pinging and the monitor alerts — without a second timer
thread. Server-liveness already has its own (upstream) timer heartbeat, so we do
not duplicate that mechanism. Alternative considered: a periodic git-sync
heartbeat thread. Rejected — redundant with the upstream one and it would ping
even while sync is silently failing.

**Port the upstream ping discipline, don't reuse the private helper.** Upstream's
`_heartbeat_ping` / `_NoRedirect` are private to `server.py`. Re-importing private
symbols couples us to their internals; instead we port the same small, audited
discipline into our `heartbeat.py`: a no-redirect opener, `read(<cap>)`, a short
timeout, and host-plus-exception-type logging (the URL can carry a secret in its
path). This is a few lines and keeps us off upstream's private surface.

**Fail-soft, fired after the push flag clears.** The ping happens after a
confirmed `push.ok`; any exception is caught and logged. A flaky monitor must
never wedge or crash the single worker thread, matching the house rule applied to
every other git operation.

## Risks / Trade-offs

- [A slow/hanging heartbeat endpoint could briefly block the single worker
  thread] → A short timeout on the opener bounds it; the worker proceeds after.
  Acceptable because pings are infrequent (once per push cycle, which is already
  debounced).
- [Commit-only deployments get no sync heartbeat] → By design: there is no push
  to confirm. The container healthcheck is the liveness signal there; documented.
- [Operators may expect the heartbeat to also mean "server alive"] → Docs
  distinguish the three layers explicitly so the right monitor is wired to the
  right signal.
