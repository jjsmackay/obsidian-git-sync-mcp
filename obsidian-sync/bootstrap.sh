#!/usr/bin/env bash
#
# Interactive one-time bootstrap for Obsidian Headless Sync, baked into the image
# at /usr/local/bin/bootstrap. Runs INSIDE the container, where `ob` and the
# config/vault volumes are already present -- so there are no docker -v flags to
# type. Bootstrap a deployed sidecar with:
#
#   docker exec -it <container> bootstrap
#
# To switch the sidecar to a DIFFERENT Obsidian account, wipe the persisted
# config/state first and bootstrap fresh in one command:
#
#   docker exec -it <container> bootstrap --reset
#
# `ob login` needs your Obsidian account (+ MFA), so this is operator-run and
# cannot be unattended. The e2e password is read with `read -rs` (no echo, no
# shell history).
#
set -euo pipefail
VAULT_PATH="${VAULT_PATH:-/vault}"
# Same expression entrypoint.sh uses, so "where config lives" never drifts.
CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"

RESET=0
case "${1:-}" in
  "") ;;
  --reset) RESET=1 ;;
  *) echo "usage: bootstrap [--reset]" >&2; exit 2 ;;
esac

if [ "$RESET" -eq 1 ]; then
  echo ">> --reset will WIPE the persisted Obsidian login + sync state in"
  echo ">> $CONFIG_DIR and bootstrap a fresh account. This is destructive."
  read -rp ">> Type 'yes' to confirm: " CONFIRM
  if [ "$CONFIRM" != "yes" ]; then
    echo ">> Aborted; nothing was changed."
    exit 0
  fi

  # Guard the path before any removal: never run against an empty value, "/", or
  # a non-directory. Wipe the CONTENTS (dotfiles included), leaving the
  # volume-mounted directory itself in place.
  if [ -z "$CONFIG_DIR" ] || [ "$CONFIG_DIR" = "/" ] || [ ! -d "$CONFIG_DIR" ]; then
    echo ">> Refusing to wipe: '$CONFIG_DIR' is not a safe config directory." >&2
    exit 1
  fi
  echo ">> Wiping $CONFIG_DIR ..."
  find "$CONFIG_DIR" -mindepth 1 -delete
fi

echo ">> Logging in to Obsidian (account + MFA)..."
ob login

echo ">> Available remote vaults:"
ob sync-list-remote
read -rp ">> Remote vault id or name to sync: " VAULT_ID

read -rsp ">> Obsidian e2e encryption password (hidden): " E2E; echo
ob sync-setup --vault "$VAULT_ID" --path "$VAULT_PATH" --password "$E2E" --device-name headless
unset E2E

ob sync-status --path "$VAULT_PATH" || true

echo
echo ">> Bootstrap complete. Restart the sidecar (or redeploy the stack) to begin"
echo ">> continuous sync."
