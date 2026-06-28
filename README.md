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

This boots the `mcp` service with git sync **disabled** — no git working tree
required yet. Enabling sync needs a bootstrapped vault repo (see below).

```bash
cp .env.example .env
# Edit .env: set VAULT_HOST_PATH (host path to your vault), VAULT_PATH
# (its path inside the container), and a strong VAULT_MCP_TOKEN.
docker compose up -d            # mcp service only
```

Copied as-is, git sync is **disabled** — a safe, bootable no-op. Before turning it
on, bootstrap the vault git repo (next section).

Every variable is annotated in [`.env.example`](.env.example), the configuration
source of truth.

## Git repo bootstrap

The worker commits against an existing git working tree — it never runs `git
init` or `git clone` for you. And startup is **fail-closed**: with
`VAULT_GIT_ENABLED=true`, the `mcp` container *refuses to boot* if `VAULT_PATH`
is not a git working tree, or if `VAULT_GIT_REMOTE` names a remote the tree does
not have. So you must seed the repo **before** enabling git sync.

`VAULT_HOST_PATH` can be any host path — `./vault`, `/srv/obsidian/vault`, a
deployment run directory. Whatever you set, that is where you clone.

**1. Clone your vault into `VAULT_HOST_PATH` on the host:**

```bash
git clone <your-vault-remote> ./vault   # match VAULT_HOST_PATH
```

**2. Give the vault a push credential** — pick one:

- **`VAULT_GIT_TOKEN` (recommended).** Set the token as a single env var; a
  credential helper hands it to git at push time, so it is **never written to the
  vault's `.git/config` and never appears on a git command line**. Use a tokenless
  remote URL; rotate by changing the one value and redeploying.

  ```bash
  git -C ./vault remote set-url origin https://github.com/<org>/<repo>.git
  # then in .env:
  VAULT_GIT_TOKEN=<TOKEN>
  ```

- **SSH deploy key.** Put the key at `./secrets/deploy_key` (`chmod 600`), set an
  SSH remote, and uncomment the key mount + `GIT_SSH_COMMAND` in
  [`docker-compose.yml`](docker-compose.yml).

  ```bash
  git -C ./vault remote set-url origin git@github.com:<org>/<repo>.git
  ```

- **Token embedded in the https remote (discouraged).** Writes the token in
  plaintext into the vault's `.git/config` on the volume, where anything that
  echoes the remote leaks it and rotation means editing a file inside the volume.
  Prefer `VAULT_GIT_TOKEN`.

  ```bash
  git -C ./vault remote set-url origin \
    https://x-access-token:<TOKEN>@github.com/<org>/<repo>.git
  ```

**3. Give the worker a commit identity.** Git refuses to commit without one, so
without an identity *every* commit fails (you'll see `git-worker sweep commit
failed (rc=128)` and nothing is committed or pushed). Either set
`VAULT_GIT_GIT_AUTHOR_NAME` + `VAULT_GIT_GIT_AUTHOR_EMAIL` in `.env`, or configure
`user.name`/`user.email` in the vault's own git config.

**4. Enable git sync** in `.env` and (re)deploy:

```bash
VAULT_GIT_ENABLED=true
VAULT_GIT_REMOTE=origin     # or leave empty for commit-only (local backup, never pushes)
```

```bash
docker compose up -d
```

> **Ordering with the obsidian-sync sidecar:** bootstrap the git tree *first* (it
> establishes the working tree + remote), then run the one-time `ob` bootstrap
> against the same `/vault` (see [`obsidian-sync/README.md`](obsidian-sync/README.md)).
> And set the **push credential before** the sidecar first syncs content down —
> otherwise the initial (large) push fails and commits pile up retrying locally.

### Named volumes (orchestrators)

The steps above assume `VAULT_HOST_PATH` is a host directory you clone into. If
instead the vault is a **Docker named volume** (e.g. a Komodo/Compose stack with
`volumes: [vault]`), you can't clone on the host — and a fresh named volume mounts
**root-owned**, so the container's non-root user (uid 10001) can't commit. Seed it
with a one-off container that clones *and* fixes ownership:

```bash
docker run --rm -v <stack>_vault:/vault <mcp-image> \
  sh -c 'git clone https://x-access-token:<TOKEN>@github.com/<org>/<repo>.git /vault \
         && git -C /vault remote set-url origin https://github.com/<org>/<repo>.git \
         && chown -R 10001:10001 /vault'
```

The `remote set-url` resets the remote to a tokenless URL so the one-off clone
token does not persist in the volume's `.git/config`; set `VAULT_GIT_TOKEN` for
the ongoing pushes. Then enable git sync and deploy as above. (The `obsidian-sync` image avoids this for
its own `config` volume by pre-creating the dir — the vault volume has no such fix.)

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

### Git-sync extension (`VAULT_GIT_*`)

Disabled by default. Set `VAULT_GIT_ENABLED` truthy to turn the extension
on, then review the rest.

| Variable | Default | Meaning |
|---|---|---|
| `VAULT_GIT_ENABLED` | _(empty / off)_ | Master switch. `true`/`1`/`yes`/`on` enables; anything else disables. |
| `VAULT_GIT_SWEEP_INTERVAL` | `60` | Seconds between periodic full-tree sweeps. Positive integer. |
| `VAULT_GIT_REMOTE` | `origin` | Remote to push to. Empty = commit-only (local backup, never pushes). |
| `VAULT_GIT_BRANCH` | _(empty)_ | Branch to push. Empty = the working tree's current branch. |
| `VAULT_GIT_TOKEN` | _(empty)_ | HTTPS push credential, supplied to git at push time by a credential helper (never written to `.git/config`, never on a command line). Required for a tokenless HTTPS remote — startup fails closed without it; not needed for SSH or an embedded-credential URL. |
| `VAULT_GIT_PUSH_DEBOUNCE` | `10` | Seconds the event queue must be quiet before the worker pushes batched commits. Positive number. |
| `VAULT_GIT_PUSH_MAX_INTERVAL` | `300` | Upper bound (seconds) on time since last push, so sustained activity still pushes periodically. Positive number. |
| `VAULT_GIT_GIT_AUTHOR_NAME` | _(empty)_ | Commit author name. Empty = git's configured identity. |
| `VAULT_GIT_GIT_AUTHOR_EMAIL` | _(empty)_ | Commit author email. Empty = git's configured identity. |
| `VAULT_GIT_STAMP` | _(empty / on)_ | Frontmatter timestamp stamping. On by default; a falsey value (`0`/`false`/`no`/`off`) commits MCP-written files unstamped. |
| `VAULT_GIT_HEARTBEAT_URL` | _(empty)_ | Optional http(s) URL pinged after each successful push. Empty = disabled; never fires in commit-only mode. |

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
- **Git-sync push heartbeat** (`VAULT_GIT_HEARTBEAT_URL`) — fired by the
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
