#!/usr/bin/env bash
# obsidian-git-sync.sh — Unified vault git sync
#
# Called by:
#   obsidian-git-sync.timer  — periodic sync (no MCP env vars set)
#   MCP post-write hook      — immediate commit (MCP_OPERATION + MCP_PATHS set)
#
# Uses flock for mutual exclusion. The MCP hook blocks (not skips) so
# mcp: commits are always preserved. The MCP response is already sent
# before the hook fires, so lock wait latency is invisible to the client.

set -euo pipefail

VAULT_DIR="/home/obsidian/Vaults/a self-hosted homelab (Sync)"
LOCK="/tmp/obsidian-git-sync.lock"
HEARTBEAT_URL="${VAULT_MCP_HEARTBEAT_URL:-}"

# Blocking flock — MCP hook waits for timer (or vice versa), never skips.
exec 200>"$LOCK"
flock 200

cd "$VAULT_DIR"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- Pull remote changes first ---
if ! git pull --rebase --autostash 2>/dev/null; then
    git rebase --abort 2>/dev/null || true

    if ! git merge origin/main -m "sync: merge remote $TS"; then
        git checkout --ours .
        git add -A
        git commit -m "sync: conflict (local wins) $TS"
    fi
fi

# --- MCP hook: commit MCP-specific paths first ---
if [ -n "${MCP_PATHS:-}" ] && [ -n "${MCP_OPERATION:-}" ]; then
    IFS=':' read -ra paths <<< "$MCP_PATHS"
    for p in "${paths[@]}"; do
        git add -- "$p" 2>/dev/null || true
    done
    if ! git diff --cached --quiet; then
        if [ ${#paths[@]} -eq 1 ]; then
            msg="mcp: ${MCP_OPERATION} ${paths[0]}"
        else
            preview=$(printf '%s, ' "${paths[@]:0:3}")
            preview=${preview%, }
            [ ${#paths[@]} -gt 3 ] && preview="$preview (+$((${#paths[@]} - 3)) more)"
            msg="mcp: ${MCP_OPERATION} ${preview}"
        fi
        git commit -m "$msg"
    fi
fi

# --- Sweep remaining changes (Headless Sync, or timer-only) ---
git add -A
if ! git diff --cached --quiet; then
    git commit -m "sync: auto $TS"
fi

# --- Push all commits in one round-trip ---
git push 2>/dev/null || {
    echo "[WARN] git push failed" >&2
}

# --- Heartbeat (timer invocation only) ---
if [ -z "${MCP_PATHS:-}" ] && [ -n "$HEARTBEAT_URL" ]; then
    curl -s "$HEARTBEAT_URL" > /dev/null 2>&1 || true
fi
