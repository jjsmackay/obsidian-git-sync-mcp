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
# Device name shown in Sync version history. Give each sidecar its own.
SYNC_DEVICE_NAME="${SYNC_DEVICE_NAME:-headless}"

# A nested sidecar (NESTED_PARENT set) must sit strictly inside the parent vault.
nested-guard

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
ob sync-setup --vault "$VAULT_ID" --path "$VAULT_PATH" --password "$E2E" --device-name "$SYNC_DEVICE_NAME"
unset E2E

# Optional sync settings, applied only when the variable is SET (an empty value
# clears the setting, e.g. SYNC_CONFIGS= turns settings sync off). Unset leaves
# ob's defaults alone. See `ob sync-config --help` for the accepted values.
if [ -n "${SYNC_CONFIGS+x}" ]; then
  ob sync-config --path "$VAULT_PATH" --configs "$SYNC_CONFIGS"
fi
if [ -n "${SYNC_FILE_TYPES+x}" ]; then
  ob sync-config --path "$VAULT_PATH" --file-types "$SYNC_FILE_TYPES"
fi

ob sync-status --path "$VAULT_PATH" || true

echo
echo ">> Bootstrap complete. Restart the sidecar (or redeploy the stack) to begin"
echo ">> continuous sync."
