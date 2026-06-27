## Why

git sync needs a home inside the running MCP server, not a second process bolted
alongside it. Upstream `obsidian-web-mcp` merged an extension seam (#57, commit
`b1da366`): `serve(extensions=[...])` loads in-process `extensions.Extension`
objects that can register tools and routes and run a post-start hook. This change
lays the foundation every later v1 change builds on — a loadable, env-gated,
fail-closed `GitSyncExtension` that boots cleanly and does nothing until the rest
of the machinery is added. Getting the scaffold and the safety contract right
first means no later change has to retrofit env-gating or startup validation.

## What Changes

- Add a Python package (uv + hatchling) exposing `GitSyncExtension(Extension)`
  that loads via `serve(extensions=[GitSyncExtension()])`.
- Depend on the upstream server (`obsidian-web-mcp`, import package
  `obsidian_vault_mcp`) via its git branch until PR #62 merges, then pin
  upstream.
- Ship our own console entry point that constructs the extension, runs
  `validate_gitsync()`, and calls `serve([GitSyncExtension()])` — mirroring the
  upstream `serve()` fail-closed pattern (`ValueError` → log → `sys.exit(1)`).
- Read all configuration from `VAULT_GIT_*` environment variables; the
  extension is **disabled by default** and is a bootable no-op when off — it
  registers nothing and the MCP server behaves exactly as upstream.
- Add `validate_gitsync()` that **fails closed**: when the extension is enabled
  but its configuration is invalid (missing repo path, bad remote, etc.), the
  server refuses to start with a clear error rather than running in a
  half-configured state.
- No change-detection, no git work, no commits yet — those arrive in later
  changes. This change ships a wired-in but inert extension.

## Capabilities

### New Capabilities
- `git-sync-extension`: the in-process extension that loads into the upstream
  MCP server — its load contract, console entry point, env-gated enable/disable,
  and fail-closed startup validation. Later v1 changes add change-detection, the
  git worker, and stamping as new requirements on this capability.

### Modified Capabilities
<!-- None — this is the first change; no existing specs. -->

## Impact

- New code: the git-sync extension package (`pyproject.toml`, the
  `GitSyncExtension` class, `validate_gitsync()`, the console entry point).
- New dependency on the upstream extension API: `extensions.Extension`,
  `serve(extensions=...)` (upstream #57, `b1da366`); declared against the fork
  branch `feat/write-listener` until PR #62 merges.
- New runtime configuration surface: the `VAULT_GIT_*` env vars (names
  provisional; aligned with `.env.example` in the container-deployment change).
- No behaviour change to the upstream server when the extension is disabled
  (the default). `/health` is reserved by upstream (auth-exempt, no handler) and
  cannot be registered by an extension — inbound liveness is deferred to the
  monitoring change.
