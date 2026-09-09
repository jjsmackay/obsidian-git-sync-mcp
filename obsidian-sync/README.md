# Obsidian Headless Sync sidecar

Runs the official [`obsidian-headless`](https://www.npmjs.com/package/obsidian-headless)
CLI (`ob`) headless, beside the `mcp` service, so **Obsidian Sync** keeps human
devices (phone, desktop) in step while the headless host serves MCP and commits
the vault working tree to git.

The sidecar is **opt-in** via the Compose `obsidian` profile. A plain
`docker compose up` runs only `mcp`; the sidecar starts only with
`--profile obsidian`.

- Image: `obsidian-sync/Dockerfile` (`node:22-bookworm-slim`, `obsidian-headless@0.0.14`).
- It mounts the **same** vault working tree as `mcp` (`${VAULT_HOST_PATH}:${VAULT_PATH}`),
  so a device edit synced down by `ob` lands on disk and the git-sync worker's
  sweep commits it.
- It persists `ob`'s config + sync state on the named volume
  `config`, mounted at `ob`'s config dir
  **`/home/ob/.config/obsidian-headless`** (credentials and the per-vault
  `state.db` live there).

## One-time bootstrap (operator step)

> **Login requires a real Obsidian account** (email/password, plus MFA if your
> account has it, and your end-to-end encryption password). This is **not**
> automated — an operator runs it once. The credentials and sync state are
> written into the `config` named volume and reused on every subsequent start;
> nothing is baked into the image.

The image carries a `bootstrap` command and an entry point that decides what to
run on start:

| On start | Behaviour |
|---|---|
| `bootstrap` arg / `BOOTSTRAP=1` | runs the interactive bootstrap |
| Already bootstrapped | `ob sync --path $VAULT_PATH --continuous` (normal) |
| Not bootstrapped | prints instructions, then polls for config — no crash-loop. Once you bootstrap, continuous sync auto-starts (no restart). |

Bootstrap is always **explicit** (the entry point never auto-starts it on a
detected TTY — compose's `tty: true` would make it hang at the login prompt with
nobody attached). It's a single command, with the volumes already mounted.

**Against a running (idle) sidecar** — the common case after `up -d`:

```bash
docker exec -it <container> bootstrap     # e.g. <stack>-sync
```

**Or as a one-off** before the sidecar is up:

```bash
docker compose --profile obsidian run --rm obsidian-sync bootstrap
```

`bootstrap` walks you through `ob login` → `ob sync-list-remote` (pick the vault
id/name) → `ob sync-setup` (prompts for the e2e password, hidden) → a status
check. You can also force it with `BOOTSTRAP=1`, or run any `ob` subcommand
directly (the entry point passes an explicit command through verbatim), e.g.
`docker compose run --rm obsidian-sync ob sync-status --path /vault`.

## Run the sidecar

Start the sidecar — the entry point detects existing config and runs continuous
sync, or idles and polls until you bootstrap:

```bash
docker compose --profile obsidian up -d
```

Effective command once bootstrapped:

```
ob sync --path /vault --continuous
```

`restart: unless-stopped` keeps it running. Until the bootstrap is done a
headless start idles with instructions (and reports unhealthy via the image
HEALTHCHECK) rather than crash-looping; after a successful bootstrap it stays up
and keeps the vault in step with Obsidian Sync.

> **Bootstrapping a running idle container auto-starts sync — no restart.** The
> idle entry point polls `CONFIG_DIR` every `SYNC_POLL_INTERVAL` seconds (default
> `5`); as soon as `docker exec … bootstrap` writes the config, the next poll
> picks it up and starts continuous sync in place. Set `SYNC_POLL_INTERVAL` to
> tune the cadence. (An explicit restart still works and is harmless.)

## Health

The image `HEALTHCHECK` asserts that sync is **currently progressing**, not just
that the sidecar was set up. In continuous mode `ob` appends a `Fully synced`
line to its per-vault `sync.log` every 30s, so the check reads that file's mtime
(never its contents) and fails once it is older than `SYNC_STALE_AFTER` seconds:

| | |
|---|---|
| Signal | newest `$CONFIG_DIR/sync/*/sync.log` mtime |
| Window | `SYNC_STALE_AFTER`, default `180` (six missed 30s beats) |
| Cadence | `--interval=30s --retries=3`, so unhealthy lands ~180-270s after the last write |
| Start period | `120s`, covering boot and the first log write |

An un-bootstrapped sidecar has no `sync.log` and so still reports unhealthy,
which is what the previous config-directory check signalled. A one-off
`bootstrap` or passthrough (`… run --rm obsidian-sync sh`) container runs no
sync session and will also read unhealthy — expected, and harmless on a
short-lived container.

Check it directly:

```bash
docker exec <container> healthcheck          # prints the age, exits 0 / 1
docker inspect --format '{{json .State.Health}}' <container>
```

### Why not a liveness probe

This check exists because of a real three-day outage. `ob` lost its connection,
logged `Connecting...`, and never reconnected — while staying **alive and
sleeping with zero open sockets**. Everything that looked at the process or its
config kept reporting healthy, and `restart: unless-stopped` never fired,
because the policy acts on a process that *exits* and this one never did. The
local file watcher carried on recording changes the whole time, so the vault
quietly diverged from every device.

The `obsidian-headless` pin was raised to `0.0.14` to fix that specific wedge
(upstream `0.0.13`: "Fix WebSocket sometimes can get stuck in CONNECTING state
indefinitely"), but the missing *signal* is the durable problem, hence this
check.

> **Detection is not recovery.** An unhealthy container is not restarted by
> Docker or Compose. To act on this automatically you need an orchestrator
> watching container health, Swarm, or an external supervisor.

## Re-bootstrap (switch account or redo)

The config volume is sticky, so the entry point keeps using whatever account is
already there. To start over — wrong account, or rotating accounts — run
`bootstrap` with `--reset`:

```bash
docker exec -it <container> bootstrap --reset     # e.g. <stack>-sync
```

`--reset` confirms first (it's destructive — it discards the stored login and
sync state under `CONFIG_DIR`), then wipes that config and falls straight through
to the normal `ob login` → `sync-setup` → status flow, so you can point the
sidecar at a different account/vault. Because the running idle entry point polls
for config, continuous sync auto-starts for the new account once the fresh
bootstrap completes — no manual restart.

(`ob logout` alone won't necessarily clear a configured vault's sync link, so the
directory wipe is the reliable reset; `--reset` guards the path so it can never
run against `/` or an empty value.)

## `ob` command reference (captured from `obsidian-headless@0.0.14`)

```
login           Login to Obsidian account or display login status
logout          Logout from Obsidian account
sync-list-remote  List available remote vaults
sync-list-local   List locally configured vaults
sync-create-remote  Create a new remote vault
sync-setup      Setup sync from a local path to a remote vault
sync-config     Change sync configuration for a vault
sync-status     Show sync status for a vault
sync-unlink     Disconnect a vault from sync and remove stored credentials
sync            Sync a vault (--continuous for long-running mode)
```

Most commands also accept `--json` (added in `0.0.14`); `sync-status` reports
static configuration only, not live connection state.
