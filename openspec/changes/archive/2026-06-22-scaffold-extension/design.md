## Context

This is the first change in the v1 decomposition. It exists because every later
change — change detection, the git worker, frontmatter stamping — needs a place
to live and a safety contract to live by. Upstream `obsidian-web-mcp` provides
that place: the extension seam merged in #57 (commit `b1da366`), which lets
`serve(extensions=[...])` load in-process `extensions.Extension` objects that can
register tools and routes and run a post-start hook.

The project descends from a single-host "bobsidian" LXC where git sync ran as
shell scripts under cron with flock for serialisation. The containerised
redesign folds that work into the MCP process. This change builds the empty
shell of that extension and nothing more: it boots, it is gated off by default,
and when gated on with bad config it refuses to start. No git work happens yet.

## Goals / Non-Goals

**Goals:**

- A `GitSyncExtension(Extension)` that loads via `serve(extensions=[...])` and
  participates cleanly in the server lifecycle.
- Configuration entirely from `VAULT_GIT_*` env vars, disabled by default,
  a true no-op when disabled.
- A `validate_gitsync()` that runs once at startup and fails closed when enabled
  with invalid config.
- An optional, config-gated `/health` route via `register_routes`.
- uv + hatchling project scaffold (`pyproject.toml`) and a unit-test harness.

**Non-Goals:**

- No change detection (`add_change_listener` / `register_write_listener`) — that
  is the change-trigger change.
- No git operations, no worker thread, no commits or pushes — those are the
  git-worker change.
- No frontmatter stamping, no Dockerfile/Compose, no monitoring heartbeat — all
  later changes.
- No MCP tools registered yet; this change may leave `register_tools` empty.

## Decisions

**In-process extension, not a sidecar process.** The whole point of the seam is
co-locating sync with the server so there is one process, one filesystem view,
and (later) one worker thread instead of flock across processes. Alternative
considered: a separate git-sync container watching the shared volume (the old
bobsidian shape). Rejected — it reintroduces cross-process serialisation, which
the locked architecture explicitly removes.

**Disabled by default, env-gated.** The package is open-source-quality and its
first consumer is a personal vault, but it must be safe to `pip install` into the
upstream image and have it do nothing until configured. A single enabling
`VAULT_GIT_*` variable gates the whole extension; everything else is read
only when enabled. Alternative considered: enabled-by-default with a disable
flag. Rejected — a no-op default is the safe failure mode for a backup/sync
add-on.

**Fail closed at exactly one place.** `validate_gitsync()` is the single point
that may abort startup, and only when the extension is enabled. This matches the
upstream #45 "house pattern". Everywhere else (the worker, later) failures are
logged and swallowed so the MCP server never crashes. Keeping the fail-closed
surface to one startup check means later changes inherit the contract without
having to re-decide it. Alternative considered: validating lazily on first git
operation. Rejected — a misconfigured backup that looks healthy until the first
write is a worse failure mode than refusing to boot.

**Our own console entry point, not the stock `vault-mcp`.** The stock entry point
runs `serve()` with no extensions. We ship our own (e.g. `obsidian-git-sync-mcp`)
that builds a `GitSyncExtension`, runs `validate_gitsync()` with the same
`ValueError → log → sys.exit(1)` handling upstream uses for `validate_config()` /
`validate_heartbeat()`, then calls `serve([ext])`. Validating in the entry point
(rather than relying on a raise inside `before_indexes_start`) yields a clean
fail-closed message instead of a raw traceback. Alternative considered:
validate only inside `before_indexes_start`. Kept as a backstop — a raise there
still propagates out of `serve()` and exits non-zero — but the entry point is the
primary, user-friendly check.

**No inbound `/health` route in this change.** `/health` is auth-exempt upstream
(reserved, no handler) and `build_app()` rejects any extension route that
collides with an exempt path — so an extension cannot serve `/health`. Inbound
liveness is therefore deferred to the monitoring change, which can use the
upstream outbound heartbeat (already built in) and/or a bearer-protected
`/gitsync/...` route. The scaffold leaves `register_routes` a no-op.

**Depend on upstream via its git branch until #62 merges.** The write listener
the later `change-trigger` change needs lives on the fork branch
`feat/write-listener` (PR #62, pending). We declare
`obsidian-web-mcp @ git+…@feat/write-listener` now and switch to an upstream pin
once #62 lands. Alternative considered: vendoring the upstream source. Rejected —
the project's stance is to consume upstream and contribute changes there, not
fork.

**uv + hatchling, Python driving the `git` CLI.** Consistent with the workspace
tooling standard and the locked architecture (no libgit2/pygit2). No git work
happens in this change, but the project scaffold is set up now so later changes
add modules rather than bootstrap packaging.

## Risks / Trade-offs

- [The upstream extension API may shift before v1 ships] → Pin to the merged #57
  surface (`serve(extensions=...)`, `register_routes`, the post-start hook at
  commit `b1da366`); contribute any needed changes upstream rather than forking.
- [Env-var names are provisional and may be renamed by the deployment change] →
  Treat names as not-yet-frozen; the container-deployment change owns
  `.env.example` and reconciles the names then. Document each variable where it
  is read.
- [A no-op default could mask a misconfiguration where the operator believes
  sync is on] → The fail-closed validation covers the enabled-but-broken case;
  the disabled case is logged at startup so the operator can see the extension
  loaded but is off.
