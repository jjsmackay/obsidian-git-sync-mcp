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
  `obsidian_sync_state`, mounted at `ob`'s config dir
  **`/home/ob/.config/obsidian-headless`** (credentials and the per-vault
  `state.db` live there).

## One-time bootstrap (operator step)

> **Login requires a real Obsidian account** (email/password, plus MFA if your
> account has it, and your end-to-end encryption password). This is **not**
> automated here — an operator runs it once. The credentials and sync state are
> written into the `obsidian_sync_state` named volume and reused on every
> subsequent start; nothing is baked into the image.

Run from the repo root (with `.env` populated as for the `mcp` service). Each
`docker compose run` uses the sidecar's build + volume mounts, so writes land in
the named volume.

1. **Log in to your Obsidian account.** Omit flags to be prompted interactively:

   ```bash
   docker compose run --rm obsidian-sync ob login
   # or non-interactively:
   # docker compose run --rm obsidian-sync ob login --email you@example.com --password '...' --mfa 123456
   ```

2. **(Optional) list your remote vaults** to get the vault id/name:

   ```bash
   docker compose run --rm obsidian-sync ob sync-list-remote
   ```

3. **Set up sync** from the mounted vault path to the chosen remote vault. The
   `--password` here is your **end-to-end encryption** password:

   ```bash
   docker compose run --rm obsidian-sync \
     ob sync-setup --vault "<remote-vault-id-or-name>" --path /vault \
                   --password '<e2e-encryption-password>' --device-name headless
   ```

   (`/vault` is `VAULT_PATH`; if you changed it, use that value.)

4. **(Optional) check status:**

   ```bash
   docker compose run --rm obsidian-sync ob sync-status --path /vault
   ```

## Run the sidecar

Once the bootstrap has populated `obsidian_sync_state`:

```bash
docker compose --profile obsidian up -d
```

The service's default command is the long-running continuous sync:

```
ob sync --path /vault --continuous
```

`restart: unless-stopped` keeps it running. Until the bootstrap is done it will
exit early reporting "No account logged in"; after a successful bootstrap it
stays up and keeps the vault in step with Obsidian Sync.

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
