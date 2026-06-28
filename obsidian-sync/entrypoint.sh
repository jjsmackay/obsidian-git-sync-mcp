#!/usr/bin/env bash
#
# Entry point for the obsidian-sync sidecar. Decides what to run:
#
#   * `bootstrap` arg, or BOOTSTRAP set   -> interactive bootstrap
#   * any other explicit command          -> run it verbatim (escape hatch, e.g.
#                                            `docker run ... <image> sh`)
#   * no command, sync configured         -> ob sync --continuous (normal mode)
#   * no command, NOT configured, TTY     -> interactive bootstrap
#   * no command, NOT configured, no TTY  -> print instructions + idle, so a
#                                            `up -d` deploy does NOT crash-loop and
#                                            you can `docker exec -it ... bootstrap`
#
set -euo pipefail
VAULT_PATH="${VAULT_PATH:-/vault}"
CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"

# Heuristic: ob writes credentials + per-vault state under CONFIG_DIR, so a
# non-empty dir means login/sync-setup has run. The image pre-creates the dir
# empty, so "empty" reliably means "not yet bootstrapped".
is_bootstrapped() { [ -n "$(ls -A "$CONFIG_DIR" 2>/dev/null)" ]; }

if [ "${1:-}" = "bootstrap" ] || [ -n "${BOOTSTRAP:-}" ]; then
  exec bootstrap
fi

# An explicit command was passed -> honour it (don't second-guess the operator).
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if is_bootstrapped; then
  exec ob sync --path "$VAULT_PATH" --continuous
fi

if [ -t 0 ]; then
  echo ">> No Obsidian sync config found and a TTY is attached -- starting bootstrap."
  exec bootstrap
fi

echo ">> obsidian-sync is NOT bootstrapped (no config in $CONFIG_DIR)."
echo ">> Run:  docker exec -it <container> bootstrap"
echo ">> Idling so the container stays up for that exec (not crash-looping)."
exec sleep infinity
