#!/usr/bin/env bash
#
# Healthcheck for the obsidian-sync sidecar.
#
# Asserts that continuous sync is CURRENTLY making progress -- not merely that
# the sidecar was once bootstrapped, and not merely that `ob` is running. Those
# weaker signals are exactly why a three-day outage went unnoticed: the client
# lost its connection, then stayed alive and sleeping with zero sockets while
# every check that looked at the process or the config dir kept saying healthy.
#
# Signal: mtime of the newest per-vault sync.log. In continuous mode `ob`
# appends a "Fully synced" line every 30s and stops the instant it stalls, so
# that file's freshness tracks sync liveness. Only the mtime is read -- the
# contents are never parsed, so changes to log wording are harmless.
#
# Deliberately NOT used; each of these reported healthy throughout the outage:
#   * process liveness      -- the process never exited, that was the whole bug
#   * `ob sync-status`      -- static config only, no connection state (0.0.14)
#   * an outbound TLS probe -- egress was provably fine; the client was wedged
#   * state.db-wal mtime    -- kept growing, because local change-tracking never
#                              stopped; only the shipping of changes did
#
# Detection is not recovery: Docker and Compose do not restart a container on
# unhealthy. See obsidian-sync/README.md.
#
set -euo pipefail

CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"
SYNC_STALE_AFTER="${SYNC_STALE_AFTER:-180}"

# Newest sync.log across all configured vaults, so a multi-vault sidecar is
# judged by its most recently active vault. The glob is unquoted and may not
# match at all (nullglob is not set), and an entry may be unreadable -- neither
# may trip `set -e`, hence the -f guard and the `|| true`.
newest_mtime=0
for log in "$CONFIG_DIR"/sync/*/sync.log; do
  [ -f "$log" ] || continue
  mtime="$(stat -c %Y "$log" 2>/dev/null || true)"
  [ -n "$mtime" ] || continue
  if [ "$mtime" -gt "$newest_mtime" ]; then
    newest_mtime="$mtime"
  fi
done

# No log at all: either never bootstrapped, or bootstrapped with sync never
# started. Both are legitimately unhealthy, which preserves the behaviour of the
# config-directory check this replaced.
if [ "$newest_mtime" -eq 0 ]; then
  echo "unhealthy: no sync.log under $CONFIG_DIR/sync/*/ (not bootstrapped, or sync never started)"
  exit 1
fi

age=$(( $(date +%s) - newest_mtime ))
if [ "$age" -ge "$SYNC_STALE_AFTER" ]; then
  echo "unhealthy: sync.log last written ${age}s ago, threshold ${SYNC_STALE_AFTER}s"
  exit 1
fi

echo "ok: sync.log written ${age}s ago (threshold ${SYNC_STALE_AFTER}s)"
