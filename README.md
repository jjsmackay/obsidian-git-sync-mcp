# obsidian-sync

Infrastructure-as-code for the Obsidian LXC at a self-hosted homelab. Manages git sync, Obsidian Headless Sync, and the Bobsidian MCP server deployment.

## Architecture

```
Obsidian devices <-> Obsidian Sync <-> LXC (Headless Sync) <-> GitHub
                                        ^
                                        |
                                   MCP Server (Bobsidian)
```

Obsidian Sync is the source of truth. The LXC runs Headless Sync to keep a local copy, and git sync pushes to GitHub for version history. The MCP server writes directly to the vault filesystem; Headless Sync propagates changes to devices, and git sync commits them to GitHub.

## Services

| Service | Unit | Description |
|---------|------|-------------|
| Headless Sync | `obsidian-headless-sync.service` | `ob sync --continuous` -- Obsidian Sync daemon |
| Git Sync | `obsidian-git-sync.timer` (5 min) | Pull remote, commit changes, push |
| MCP Server | `obsidian-mcp.service` | Bobsidian -- vault read/write over MCP |
| Headless Heartbeat | cron (1 min) | Uptime Kuma push if sync log is fresh |

## Commit Convention

| Prefix | Source |
|--------|--------|
| `mcp: created/updated/deleted/moved ...` | MCP write via post-write hook |
| `sync: auto <timestamp>` | Periodic Headless Sync changes |
| `sync: merge remote <timestamp>` | Clean merge from GitHub |
| `sync: conflict (local wins) <timestamp>` | Headless Sync overrode remote |

## Setup

```bash
sudo bash /home/obsidian/obsidian-sync/scripts/setup.sh
```

See the script for details. It's idempotent -- safe to re-run.

## Host Details

| | |
|--|--|
| Host | Proxmox LXC (Debian 13 Trixie) |
| Hostname | `obsidian` / `${HOST_NAME}` |
| IP | `${HOST_IP}` |
| User | `obsidian` |
| Vault | `/home/obsidian/Vaults/a self-hosted homelab (Sync)/` |
| GitHub | `${VAULT_REPO}` |
