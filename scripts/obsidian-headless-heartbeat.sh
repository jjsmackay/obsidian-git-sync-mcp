#!/usr/bin/env bash
# obsidian-headless-heartbeat.sh — Ping Uptime Kuma if Headless Sync is active
#
# Runs via cron every minute. Only pings if the sync log was modified
# in the last 5 minutes. If ob dies or disconnects, the log goes stale,
# heartbeat stops, Uptime Kuma alerts.
#
# Crontab entry (obsidian user):
#   * * * * * /home/obsidian/obsidian-sync/scripts/obsidian-headless-heartbeat.sh

set -euo pipefail

ENV_FILE="/home/obsidian/.config/obsidian-sync/env"
# shellcheck source=/dev/null
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

HEARTBEAT_URL="${OBSIDIAN_HEADLESS_HEARTBEAT_URL:-}"
LOG_DIR="/home/obsidian/.config/obsidian-headless/sync"

if [ -z "$HEARTBEAT_URL" ]; then
    exit 0
fi

# Find the sync log (vault ID directory varies)
LOG=$(find "$LOG_DIR" -name "sync.log" -mmin -5 2>/dev/null | head -1)

if [ -n "$LOG" ]; then
    curl -s "$HEARTBEAT_URL" > /dev/null 2>&1 || true
fi
