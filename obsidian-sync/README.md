# Obsidian Headless Sync sidecar

Runs the official [`obsidian-headless`](https://www.npmjs.com/package/obsidian-headless)
CLI (`ob`) headless, beside the `mcp` service, so **Obsidian Sync** keeps human
devices (phone, desktop) in step while the headless host serves MCP and commits
the vault working tree to git.

The sidecar is **opt-in** via the Compose `obsidian` profile. A plain
`docker compose up` runs only `mcp`; the sidecar starts only with
`--profile obsidian`.

- Image: `obsidian-sync/Dockerfile` (`node:22-bookworm-slim`, `obsidian-headless@0.0.12`).
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
| Already bootstrapped | `ob sync --path $VAULT_PATH --continuous` (normal) |
| Not bootstrapped, **TTY** attached | runs `bootstrap` interactively |
| Not bootstrapped, **no TTY** (`up -d`) | prints instructions and idles — no crash-loop |

So bootstrap is a single interactive command, with the volumes already mounted.

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

Once `config` is populated, start (or restart) the sidecar — the entry point
detects the config and runs continuous sync:

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

## `ob` command reference (captured from `obsidian-headless@0.0.12`)

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
