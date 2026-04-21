# bobsidian

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
| Headless Sync | `obsidian-sync.service` | `ob sync --continuous` — Obsidian Sync daemon |
| Git Sync | `obsidian-git.timer` (5 min) | Pull remote, commit changes, push |
| MCP Server | `obsidian-mcp.service` | Bobsidian — vault read/write over MCP |
| Headless Heartbeat | cron (1 min) | Uptime Kuma push if sync log is fresh |
| MCP Heartbeat | `obsidian-mcp.service` (in-process task) | Uptime Kuma push while MCP is running (opt-in via env) |

**Naming note:** The `ob` CLI is the [`obsidian-headless`](https://www.npmjs.com/package/obsidian-headless) npm package (not `obsidian-sync`). Two nearby-but-distinct paths:

| Path | Owner | Contents |
|------|-------|----------|
| `~/.config/obsidian-headless/` | `ob` CLI (npm package) | Login credentials, per-vault `state.db`, `sync/<vault-id>/sync.log` |
| `~/.config/obsidian-sync/` | This repo | Our env file (`GIT_SYNC_HEARTBEAT_URL`, `OBSIDIAN_SYNC_HEARTBEAT_URL`) |

If you're troubleshooting `ob` state, look in `obsidian-headless/`. If you're editing heartbeat URLs, look in `obsidian-sync/`.

## Commit Convention

| Prefix | Source |
|--------|--------|
| `mcp: created/updated/deleted/moved/patched/appended ...` | MCP write via post-write hook |
| `sync: auto <timestamp>` | Periodic Headless Sync changes |
| `sync: merge remote <timestamp>` | Clean merge from GitHub |
| `sync: conflict (local wins) <timestamp>` | Headless Sync overrode remote |

## Frontmatter Stamping

MCP writes are stamped with `created` / `modified` timestamps in the `git-sync.sh` pre-commit step, so notes authored or edited via the MCP carry the same metadata as notes edited in the desktop app (which are stamped by the Linter community plugin).

| Field | Behaviour |
|-------|-----------|
| `created` | Set only if missing |
| `modified` | Always bumped to the current UTC time |

Format: `YYYY-MM-DDTHH:mm:ssZ` (unquoted), matching the Linter plugin so quote-style churn doesn't trigger spurious diffs. Deletes, non-markdown paths, and missing files are skipped.

Implementation: `scripts/stamp-frontmatter.py` (PEP 723 uv script, `ruamel.yaml`). Invoked from `git-sync.sh` against `MCP_PATHS` before `git add`.

## Host Details

| | |
|--|--|
| Host | Proxmox LXC (Debian 13 Trixie) |
| Hostname | `obsidian` / `${HOST_NAME}` |
| IP | `${HOST_IP}` |
| User | `bobsidian` |
| Vault | `/home/bobsidian/obsidian-vault/` |
| GitHub | `${VAULT_REPO}` |
| Obsidian Sync host | `sync-37.obsidian.md` |

## Deployment

The LXC itself and the `bobsidian` user are provisioned manually in Proxmox. Everything from that point is handled by this repo.

### 1. Pre-flight (one-time, manual)

On the LXC, as root:

```bash
# Create the bobsidian user if it doesn't exist
id bobsidian || adduser --disabled-password --gecos "" bobsidian
usermod -aG sudo bobsidian

# Set a password so sudo works. --disabled-password above skips this;
# without it, `sudo -u bobsidian ...` from root is fine but bobsidian
# can't invoke sudo themselves (e.g. for `sudoedit`).
passwd bobsidian
```

Generate an SSH deploy key for GitHub (as `bobsidian`):

```bash
sudo -u bobsidian ssh-keygen -t ed25519 -N "" -f /home/bobsidian/.ssh/id_ed25519
sudo -u bobsidian cat /home/bobsidian/.ssh/id_ed25519.pub
```

Add the public key to the `${VAULT_REPO}` repo on GitHub as a **Deploy Key with write access** (Settings → Deploy keys).

Verify:

```bash
sudo -u bobsidian ssh -T git@github.com
```

### 2. Bootstrap

Clone this repo and run the setup script:

```bash
sudo -u bobsidian git clone https://github.com/${PROJECT_REPO}.git /home/bobsidian/obsidian-sync
sudo bash /home/bobsidian/obsidian-sync/scripts/setup.sh
```

The script is idempotent (safe to re-run). It:

- Installs `ripgrep`, `git`, `curl`
- Installs `uv` for the `bobsidian` user
- Clones/updates `obsidian-web-mcp` and `bobsidian`
- Sets git identity (Bobsidian) in the vault repo if present
- Creates env file templates at `/home/bobsidian/.config/obsidian-mcp/env` and `/home/bobsidian/.config/obsidian-sync/env`
- Installs all systemd units and enables them
- Installs the headless heartbeat cron job
- Pre-warms the Python virtualenv and the frontmatter stamper

### 3. Fill in env files

```bash
sudoedit /home/bobsidian/.config/obsidian-mcp/env
sudoedit /home/bobsidian/.config/obsidian-sync/env
```
Required values in `obsidian-sync/env`:

- `GIT_SYNC_HEARTBEAT_URL` — Uptime Kuma push URL for git sync monitor (use the **internal** Kuma hostname, e.g. `http://${MONITOR_HOST}:3001/...` — the public hostname is behind Cloudflare Access and will bounce unauthenticated pushes)
- `OBSIDIAN_SYNC_HEARTBEAT_URL` — Uptime Kuma push URL for headless sync monitor (same: internal hostname)

Required values in `obsidian-mcp/env`:

- `VAULT_MCP_TOKEN` — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `VAULT_OAUTH_CLIENT_SECRET` — generate same way
- `VAULT_MCP_ALLOWED_HOSTS` — your Cloudflare Tunnel public hostname
- `VAULT_PUBLIC_BASE_URL` — full public origin the tunnel serves (e.g. `https://${PUBLIC_HOST}`). Needed so OAuth metadata advertises https URLs rather than deriving from request headers

Optional values in `obsidian-mcp/env`:

- `VAULT_MCP_HEARTBEAT_URL` + `VAULT_MCP_HEARTBEAT_INTERVAL` — MCP server's own Kuma push heartbeat. Alerts on MCP-specific outages (distinct from git sync / headless — those can be healthy while the MCP process is wedged). Set up the matching `(Obsidian) MCP` monitor in Step 6
- `VAULT_MCP_STATELESS` (default `true`) / `VAULT_MCP_PATH` (default `/mcp`) — transport tuning. Defaults match what Claude's remote connector needs; only override if you know why

### 4. Headless Sync — one-time interactive setup

Two interactive steps before `obsidian-sync.service` can start. Both are one-time.

**4a. Log in** — stores credentials in `~/.config/obsidian-headless/`:

```bash
sudo -u bobsidian ob login
# follow prompts — email + password for the Obsidian account
```

**4b. Pair the local path to a remote vault** — `obsidian-sync.service` runs `ob sync --path /home/bobsidian/obsidian-vault --continuous`, which refuses to start until that path is registered as a sync target:

```bash
sudo -u bobsidian mkdir -p /home/bobsidian/obsidian-vault
sudo -u bobsidian ob sync-setup --path /home/bobsidian/obsidian-vault
# pick the vault from the list, confirm the encryption password if prompted
```

Verify:

```bash
ls /home/bobsidian/.config/obsidian-headless/
# should show a vault-ID directory containing state.db
```

### 5. Vault git history

Headless Sync populates the vault dir with cloud content on first run but doesn't initialise git — `obsidian-git.timer` needs a git repo at `VAULT_DIR`, otherwise every tick fails silently. Do this **before** starting the timer in Step 7; if the timer is running already (re-deploy / recovery), stop it first so a tick can't fire mid-dance and commit broken state:

```bash
sudo systemctl stop obsidian-git.timer    # no-op on a fresh deploy
```

Seed git history from GitHub:

```bash
cd /home/bobsidian/obsidian-vault
sudo -u bobsidian git init -b main
sudo -u bobsidian git remote add origin git@github.com:${VAULT_REPO}.git
sudo -u bobsidian git fetch origin main
sudo -u bobsidian git reset origin/main                  # adopt GitHub HEAD, keep working tree
sudo -u bobsidian git checkout HEAD -- .gitignore        # restore dotfiles (see note below)
```

Any drift between cloud state and GitHub's last commit now shows as uncommitted changes. The first `obsidian-git.timer` tick commits them as `sync: auto` and pushes — the catch-up push that reconciles GitHub to cloud truth.

**Why the `.gitignore` checkout:** Obsidian Sync doesn't replicate dotfiles, so `.gitignore` never lands in the working tree via Headless Sync. After `git reset origin/main`, git sees it as "deleted" — if you skip the restore, the next timer tick commits that deletion and propagates it to GitHub. The explicit `checkout HEAD -- .gitignore` re-materialises it from the just-fetched tree.

**Ordering rule:** vault must be a valid git repo **before** `obsidian-git.timer` starts. Keep the timer stopped until Step 7.

### 6. Uptime Kuma monitors

Create Push-type monitors in Uptime Kuma and paste their URLs into the env files:

| Name | Interval | Retries | Push URL goes in | Notes |
|------|----------|---------|------------------|-------|
| `Obsidian Headless Sync` | 120s | 3 | `obsidian-sync/env` (`OBSIDIAN_SYNC_HEARTBEAT_URL`) | Cron runs every minute, pings only if sync log fresh |
| `Obsidian Git Sync` | 600s | 3 | `obsidian-sync/env` (`GIT_SYNC_HEARTBEAT_URL`) | Timer runs every 5 min, pings unconditionally |
| `(Obsidian) MCP` | 120s | 3 | `obsidian-mcp/env` (`VAULT_MCP_HEARTBEAT_URL`) | MCP process pings itself every 60s while running (optional — skip if you only care about sync health) |

### 7. Start services

```bash
sudo systemctl start obsidian-sync
sudo systemctl start obsidian-git.timer
sudo systemctl start obsidian-mcp
```

### 8. Cloudflare Tunnel

Configure the tunnel to route the **entire public hostname** (e.g. `${PUBLIC_HOST}`) to `http://localhost:8420` on the LXC. This is done in the Cloudflare Zero Trust dashboard — not handled by this repo.

**Do not path-scope the rule to `/mcp`.** OAuth discovery requests hit `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource` at the hostname root — a `/mcp`-scoped rule makes those 404, and Claude's connector fails to authenticate with no obvious error. Route hostname-wide and let the MCP server answer its own paths.

### 9. Claude custom connector

In Claude (claude.ai/settings/connectors), add a custom MCP server:

| | |
|--|--|
| Name | Bobsidian |
| URL | `https://<tunnel-hostname>/mcp` |
| Client ID | value of `VAULT_OAUTH_CLIENT_ID` (default: `bobsidian`) |
| Client Secret | value of `VAULT_OAUTH_CLIENT_SECRET` |

## Verification

```bash
# All services running?
systemctl status obsidian-sync obsidian-mcp
systemctl status obsidian-git.timer

# Heartbeat cron installed? (setup.sh can silently skip if re-run against a partial state)
sudo -u bobsidian crontab -l | grep heartbeat.sh
# Expect: * * * * * /home/bobsidian/obsidian-sync/scripts/heartbeat.sh

# Recent logs
journalctl -u obsidian-mcp -n 50
journalctl -u obsidian-sync -n 50
journalctl -u obsidian-git --since "10 min ago"

# MCP heartbeat wired? (only if VAULT_MCP_HEARTBEAT_URL is set)
journalctl -u obsidian-mcp --no-pager | grep "Heartbeat enabled"
# Expect: "Heartbeat enabled (interval: 60s)" once per MCP session init

# Test MCP write — make a small change via Claude, then check:
git -C "/home/bobsidian/obsidian-vault" log --oneline -5
# Expect to see an "mcp:" commit at the top
```

## Troubleshooting

### Headless Sync stuck / disconnected

```bash
tail -20 /home/bobsidian/.config/obsidian-headless/sync/*/sync.log
```

If stuck on "Connecting..." or last entry is old:

```bash
sudo systemctl restart obsidian-sync
```

### "Another sync instance is already running"

Stale lock after unclean shutdown. The `state.db` holds the lock. Restart the service (which replaces the process) rather than running `ob` manually:

```bash
sudo systemctl restart obsidian-sync
```

### Git Sync not pushing

```bash
systemctl status obsidian-git.timer
journalctl -u obsidian-git --no-pager -n 20
```

Check SSH auth:

```bash
sudo -u bobsidian ssh -T git@github.com
```

### MCP server not responding

```bash
journalctl -u obsidian-mcp -f
# look for bind errors, token issues, missing env vars
```

Verify port:

```bash
ss -tlnp | grep 8420
```

### Missing files after restart

Headless Sync only runs when `ob` is active. If the service was down, files won't appear until it reconnects and downloads. After restarting, wait 30-60s and check the log for "Fully synced".

### Timer and MCP hook fighting

Both invoke `git-sync.sh` and coordinate via flock at `/tmp/obsidian-git.lock`. If you suspect a stuck lock:

```bash
lsof /tmp/obsidian-git.lock
# Only if no process holds it:
rm /tmp/obsidian-git.lock
```

## Updating

Pull latest and re-run setup:

```bash
sudo -u bobsidian git -C /home/bobsidian/obsidian-sync pull
sudo -u bobsidian git -C /home/bobsidian/obsidian-mcp pull
sudo bash /home/bobsidian/obsidian-sync/scripts/setup.sh
sudo systemctl daemon-reload
sudo systemctl restart obsidian-mcp
```

Env file changes and systemd unit changes both require restart. The `daemon-reload` picks up unit changes.
