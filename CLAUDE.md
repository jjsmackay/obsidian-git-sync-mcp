# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Infrastructure-as-code for the Obsidian LXC (`${HOST_NAME}`, ${HOST_IP}) hosting a self-hosted Obsidian vault. It installs and wires together three long-running services on a Debian 13 Proxmox container as the `bobsidian` user. The repo itself has no build or test suite — it is shell scripts, systemd units, and an env-file templating layer.

The MCP server code lives in a separate repo (`${MCP_REPO}`), which `setup.sh` clones alongside this one. This repo only deploys it.

**No `just`, `make`, or package scripts.** Work is validated by running `bash -n scripts/<script>.sh` for syntax and by running `scripts/stamp-frontmatter.py` directly against a sample file:

```bash
uv run --script scripts/stamp-frontmatter.py /path/to/note.md
```

## Architecture

```
Obsidian devices <-> Obsidian Sync <-> LXC (ob Headless Sync) <-> GitHub
                                         ^
                                         |
                                    MCP Server (writes to vault filesystem)
```

- **Obsidian Sync is the source of truth.** Devices read/write through it; the LXC stays in sync via `ob sync --continuous`.
- **MCP Server** writes directly to `/home/bobsidian/obsidian-vault/`. Headless Sync detects the change and propagates it to devices. A post-write hook fires `git-sync.sh` so GitHub sees it immediately instead of waiting for the 5-minute timer.
- **Git sync** is a mirror for version history, not a sync path. Clients never pull from or push to GitHub directly.

### Three processes that all touch the vault

| Process | Unit | Cadence | Writes |
|---------|------|---------|--------|
| Headless Sync | `obsidian-sync.service` | continuous | vault files from cloud |
| Git Sync | `obsidian-git.timer` | every 5 min | git commits + push |
| MCP Server | `obsidian-mcp.service` | on request | vault files + triggers git-sync.sh |

Headless Sync and the MCP Server can both modify the working tree at any moment, and the git-sync script is invoked by both the timer and the MCP post-write hook. Coordination matters — see next section.

## The git-sync.sh Concurrency Model

`scripts/git-sync.sh` is the only thing in this repo with non-obvious logic. Read it before editing.

- **Flock at `/tmp/obsidian-git.lock`** serialises the timer and MCP-hook invocations. It is a *blocking* flock — whichever starts second waits, never skips.
- **Two-phase commit:** if MCP env vars (`MCP_OPERATION`, `MCP_PATHS`) are set, those paths are stamped + committed first as `mcp: <op> <paths>`. A second `git add -A` sweep catches anything Headless Sync dropped and commits it as `sync: auto <ts>`.
- **Conflict policy — local wins.** After committing, the script fetches and `git rebase -X theirs origin/main`. During a rebase, "theirs" = the commits being replayed (ours), so this resolves conflicts in favour of what the LXC just committed. Rationale: Obsidian Sync is the source of truth, GitHub is the mirror.
- **Why rebase, not stash/pop:** a failed stash pop can silently leave conflict markers in the working tree, which the next `git add -A` would then commit and push. Rebase fails loudly and is aborted cleanly.
- **Push failures are tolerated** (logged, not fatal). Network blips must not cause the timer to start skipping ticks — the next tick catches up.

If you change conflict handling, preserve the invariant: **the working tree must never be committed with unresolved conflict markers.**

## Commit Message Convention

Generated, not written by hand. Keep this shape if you modify `git-sync.sh`:

| Prefix | Source |
|--------|--------|
| `mcp: <operation> <paths>` | MCP post-write hook |
| `sync: auto <timestamp>` | Timer sweep of Headless Sync changes |

Remote commits (from GitHub) retain their original messages after rebase; there is no explicit "merge remote" or "conflict" prefix emitted by `git-sync.sh`.

## Frontmatter Stamping

`scripts/stamp-frontmatter.py` is a PEP 723 uv script (inline deps, runnable via `uv run --script`). It upserts `created` (set once) and `modified` (always bumped) on markdown files before they are committed by the MCP hook path. Non-markdown files and deletes are skipped silently.

**Format contract with the Obsidian Linter plugin:** `YYYY-MM-DDTHH:mm:ssZ` unquoted, UTC. If quote style drifts, desktop-side Linter stamps and LXC-side stamps will churn against each other on every edit. Do not switch to ISO formats with `+00:00` or quote the timestamps.

## Two `.config/` Directories — Do Not Conflate

| Path | Owner | What's in it |
|------|-------|--------------|
| `~/.config/obsidian-headless/` | the `ob` CLI (npm `obsidian-headless` package) | login credentials, per-vault `state.db`, `sync/<vault-id>/sync.log` |
| `~/.config/obsidian-sync/` | this repo | `env` file with heartbeat URLs |

The `ob` CLI is named `obsidian-headless` on npm, not `obsidian-sync`. Our env file directory shares the "sync" name with the systemd service, not with the upstream tool.

## Deployment Model

- The LXC and `bobsidian` user are provisioned manually in Proxmox (one-time).
- Everything else runs from `scripts/setup.sh` as root. It is idempotent — safe to re-run after pulling changes.
- Env files live outside this repo (`/home/bobsidian/.config/obsidian-{mcp,sync}/env`, chmod 600). `setup.sh` seeds them from the `env/*.env.example` templates if missing.
- Post-deploy steps that `setup.sh` cannot automate (interactive): `ob login`, `ob sync-setup`, and seeding git history from GitHub. See README.md §2–§5 for the full bootstrap sequence.

### Updating a running LXC

```bash
sudo -u bobsidian git -C /home/bobsidian/obsidian-sync pull
sudo -u bobsidian git -C /home/bobsidian/obsidian-mcp pull
sudo bash /home/bobsidian/obsidian-sync/scripts/setup.sh
sudo systemctl daemon-reload
sudo systemctl restart obsidian-mcp    # systemd unit changes need daemon-reload + restart
```

## Monitoring

Three possible Uptime Kuma Push monitors — the first two are wired by this repo, the third is optional:

| Monitor | Pushed by | When |
|---------|-----------|------|
| Obsidian Git Sync | `git-sync.sh` | every successful timer tick (not on MCP hook invocations) |
| Obsidian Headless Sync | `heartbeat.sh` (cron, every minute) | only if `sync.log` was modified within 5 min |
| (Obsidian) MCP | the MCP server itself, if `VAULT_MCP_HEARTBEAT_URL` set | every `VAULT_MCP_HEARTBEAT_INTERVAL` seconds |

**Use internal Kuma hostnames in env files.** Public Kuma is behind Cloudflare Access and will return a login redirect instead of accepting the push. Wrap push URLs in double quotes so `&` separators don't break `source`.

## Cloudflare Tunnel

The tunnel must route the **entire public hostname** to `http://localhost:8420`, not just `/mcp`. OAuth discovery hits `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource` at the hostname root; a `/mcp`-scoped rule makes those 404 with no obvious error in Claude's connector UI.

## Editing Scope

- `scripts/` and `systemd/` are the payload — changes here ship to the LXC on the next `setup.sh` run.
- `env/*.env.example` are templates only. Real values live on the LXC and must never be committed.
- The MCP server source is not in this repo. Fix MCP bugs in `${MCP_REPO}`.
