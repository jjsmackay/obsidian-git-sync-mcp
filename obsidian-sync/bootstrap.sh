#!/usr/bin/env bash
#
# Interactive one-time bootstrap for Obsidian Headless Sync, baked into the image
# at /usr/local/bin/bootstrap. Runs INSIDE the container, where `ob` and the
# config/vault volumes are already present -- so there are no docker -v flags to
# type. Bootstrap a deployed sidecar with:
#
#   docker exec -it <container> bootstrap
#
# `ob login` needs your Obsidian account (+ MFA), so this is operator-run and
# cannot be unattended. The e2e password is read with `read -rs` (no echo, no
# shell history).
#
set -euo pipefail
VAULT_PATH="${VAULT_PATH:-/vault}"

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
