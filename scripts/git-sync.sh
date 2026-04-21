#!/usr/bin/env bash
# git-sync.sh — Unified vault git sync
#
# Called by:
#   obsidian-git.timer  — periodic sync (no MCP env vars set)
#   MCP post-write hook — immediate commit (MCP_OPERATION + MCP_PATHS set)
#
# Pattern: commit local changes first, then rebase onto remote, then push.
# Obsidian Sync is the source of truth; on rebase conflicts, local wins
# via `-X theirs` (during rebase, "theirs" = the commits being replayed,
# i.e. our sync/mcp commits). This avoids the stash-pop trap where a
# failed pop can leave conflict markers in the working tree that then
# get auto-committed and pushed.
#
# Flock serialises MCP and timer invocations.

set -euo pipefail

VAULT_DIR="/home/bobsidian/obsidian-vault"
LOCK="/tmp/obsidian-git.lock"
HEARTBEAT_URL="${GIT_SYNC_HEARTBEAT_URL:-}"
STAMP_SCRIPT="$(dirname "$(readlink -f "$0")")/stamp-frontmatter.py"

# Blocking flock — MCP hook waits for timer (or vice versa), never skips.
exec 200>"$LOCK"
flock 200

cd "$VAULT_DIR"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- MCP hook: commit MCP-specific paths first (with frontmatter stamp) ---
if [ -n "${MCP_PATHS:-}" ] && [ -n "${MCP_OPERATION:-}" ]; then
    IFS=':' read -ra paths <<< "$MCP_PATHS"

    if [ "${MCP_OPERATION}" != "deleted" ] && [ -x "$STAMP_SCRIPT" ]; then
        "$STAMP_SCRIPT" "${paths[@]}" || true
    fi

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

# --- Incorporate external writes from GitHub ---
# Fetch; rebase local commits onto origin/main with sync-wins conflict policy.
# `-X theirs` during rebase favours the replayed commits (our commits above).
# If fetch fails (network), skip the rebase and try to push anyway.
if git fetch origin 2>/dev/null; then
    if ! git rebase -X theirs origin/main 2>/dev/null; then
        git rebase --abort 2>/dev/null || true
        echo "[WARN] rebase of origin/main failed; manual intervention required" >&2
    fi
fi

# --- Push all commits in one round-trip ---
git push 2>/dev/null || {
    echo "[WARN] git push failed" >&2
}

# --- Heartbeat (timer invocation only) ---
if [ -z "${MCP_PATHS:-}" ] && [ -n "$HEARTBEAT_URL" ]; then
    curl -s "$HEARTBEAT_URL" > /dev/null 2>&1 || true
fi
