# obsidian-git-sync-mcp

A dockerised, self-hostable host that runs an Obsidian vault headlessly and
serves it to MCP clients, with pluggable sync (git first).

It writes the vault filesystem directly, through the upstream
[`obsidian-web-mcp`](https://github.com/jimprosser/obsidian-web-mcp) server, so
it is headless, containerisable, and sync-agnostic. That is the difference from
the common Obsidian MCP servers that drive the Obsidian desktop app via its
Local REST API plugin: those need a running desktop, a GUI session, and the
plugin. This one needs none of that — it serves a vault on disk, mirrors history
to git as a backup and audit trail, and (optionally) keeps human devices in step
via Obsidian Sync.

## Architecture

The process is the upstream `obsidian-web-mcp` server with an in-process
`GitSyncExtension` loaded through its extension seam (`serve([ext])`). The
extension classifies vault changes into two event streams and funnels them to a
single git worker:

- **MCP writes** — files the upstream server writes on behalf of an MCP client,
  committed with `mcp:` messages.
- **Sweeps** — a `.md` change watcher plus a periodic timer that walks the whole
  tree (catching attachments and canvas the `.md` watcher cannot see), committed
  with `sync:` messages.

One git worker thread performs all git work: stage, commit, then a debounced
local-wins rebase and push. MCP-written files can optionally have their
frontmatter timestamp stamped before commit.

The Docker stack is two containers: an always-on `mcp` service, and an optional
`obsidian-sync` sidecar (opt-in via a Compose profile) that runs Obsidian
Headless Sync against the same vault working tree.

## Quickstart

The vault must be a git working tree (the worker commits against it).

```bash
cp .env.example .env
# Edit .env: set VAULT_HOST_PATH (host path to your vault), VAULT_PATH
# (its path inside the container), and a strong VAULT_MCP_TOKEN.
docker compose up -d            # mcp service only
```

Copied as-is, git sync is **disabled** — a safe, bootable no-op. To turn it on,
set in `.env`:

```bash
VAULT_GITSYNC_ENABLED=true
VAULT_GITSYNC_REMOTE=origin     # or leave empty for commit-only (local backup, never pushes)
```

Pushing needs a credential the image must not bake in — mount an SSH deploy key
or use a token-bearing https remote configured in the vault. See the comments in
[`docker-compose.yml`](docker-compose.yml).

Every variable is annotated in [`.env.example`](.env.example), the configuration
source of truth.

## Configuration

### Upstream server (`VAULT_*`)

These belong to the upstream `obsidian-web-mcp` server; the deployment needs
them.

| Variable | Default | Meaning |
|---|---|---|
| `VAULT_PATH` | `/vault` | Path to the vault git working tree **inside the container**. |
| `VAULT_HOST_PATH` | `./vault` | Host path mapped to `VAULT_PATH` (Compose-only). |
| `VAULT_MCP_TOKEN` | — | Bearer token MCP clients must present. Required; set a strong random value. |
| `VAULT_MCP_PORT` | `8420` | Port the MCP transport listens on (and the port Compose publishes). |
| `VAULT_MCP_HOST` | `0.0.0.0` | Bind address. Must bind all interfaces inside a container to be reachable. |
| `VAULT_MCP_ALLOWED_HOSTS` | — | Extra hostnames allowed through DNS-rebinding protection (comma-separated). Add your proxy/tunnel hostname. |
| `VAULT_MCP_PUBLIC_URL` | — | Canonical public origin advertised in OAuth discovery and auth challenges. Empty = derive per request. |
| `VAULT_OAUTH_*` | see `.env.example` | Optional OAuth (client id/secret, login gate, redirect URIs) for the Claude app browser integration. |

### Git-sync extension (`VAULT_GITSYNC_*`)

Disabled by default. Set `VAULT_GITSYNC_ENABLED` truthy to turn the extension
on, then review the rest.

| Variable | Default | Meaning |
|---|---|---|
| `VAULT_GITSYNC_ENABLED` | _(empty / off)_ | Master switch. `true`/`1`/`yes`/`on` enables; anything else disables. |
| `VAULT_GITSYNC_SWEEP_INTERVAL` | `60` | Seconds between periodic full-tree sweeps. Positive integer. |
| `VAULT_GITSYNC_REMOTE` | `origin` | Remote to push to. Empty = commit-only (local backup, never pushes). |
| `VAULT_GITSYNC_BRANCH` | _(empty)_ | Branch to push. Empty = the working tree's current branch. |
| `VAULT_GITSYNC_PUSH_DEBOUNCE` | `10` | Seconds the event queue must be quiet before the worker pushes batched commits. Positive number. |
| `VAULT_GITSYNC_PUSH_MAX_INTERVAL` | `300` | Upper bound (seconds) on time since last push, so sustained activity still pushes periodically. Positive number. |
| `VAULT_GITSYNC_GIT_AUTHOR_NAME` | _(empty)_ | Commit author name. Empty = git's configured identity. |
| `VAULT_GITSYNC_GIT_AUTHOR_EMAIL` | _(empty)_ | Commit author email. Empty = git's configured identity. |
| `VAULT_GITSYNC_STAMP` | _(empty / on)_ | Frontmatter timestamp stamping. On by default; a falsey value (`0`/`false`/`no`/`off`) commits MCP-written files unstamped. |
| `VAULT_GITSYNC_HEARTBEAT_URL` | _(empty)_ | Optional http(s) URL pinged after each successful push. Empty = disabled; never fires in commit-only mode. |

## Obsidian Sync sidecar

The optional `obsidian-sync` sidecar runs Obsidian Headless Sync against the
same vault working tree, so a device edit synced down lands on disk where the
git-sync sweep commits it. It is opt-in via the Compose `obsidian` profile
(`docker compose --profile obsidian up -d`) and needs a one-time interactive
bootstrap that requires a real Obsidian account login. See
[`obsidian-sync/README.md`](obsidian-sync/README.md) for the bootstrap.

## Exposure

Compose publishes **only** the MCP port; nothing else is exposed to the host. No
tunnel is baked into the project. For remote access, put a reverse proxy,
Cloudflare Tunnel, or Tailscale in front of the published port, then:

- add the public hostname to `VAULT_MCP_ALLOWED_HOSTS` (so DNS-rebinding
  protection lets it through), and
- set `VAULT_MCP_PUBLIC_URL` to the canonical public origin (so OAuth discovery
  and auth challenges are pinned against Host spoofing).

Do not expose the published port directly to the internet.

## Monitoring

Three independent layers, each answering a different question:

- **Container healthcheck** — a dependency-free TCP connect to the MCP port,
  baked into the image `HEALTHCHECK` (so `docker compose ps` reports health).
  Answers: is the port accepting connections?
- **Upstream liveness heartbeat** (`VAULT_MCP_HEARTBEAT_URL`) — the upstream
  server's outbound liveness ping. Answers: is the server process alive?
- **Git-sync push heartbeat** (`VAULT_GITSYNC_HEARTBEAT_URL`) — fired by the
  worker after each successful push. Answers: is sync actually reaching the
  remote? (Never fires in commit-only mode.)

## Development

```bash
uv sync --extra dev
uv run pytest
```

This project consumes the upstream `obsidian-web-mcp` server and contributes
changes upstream rather than forking it. It loads through the upstream extension
seam (PR #57) and uses the write listener on the `feat/write-listener` branch
(PR #62); until that merges, the dependency is pinned to that git branch in
[`pyproject.toml`](pyproject.toml) and will be repinned to a released version
once it lands.

Development is spec-driven via [OpenSpec](https://github.com/Fission-AI/OpenSpec)
— proposals, designs, and specs live under `openspec/`.

## Licence

MIT — see [LICENSE](LICENSE).
