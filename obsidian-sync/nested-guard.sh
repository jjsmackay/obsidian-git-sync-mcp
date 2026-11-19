#!/usr/bin/env bash
#
# Guard for a NESTED sidecar: a second `ob` client that syncs one folder of the
# vault to its own remote (e.g. a team-shared folder inside a private vault),
# while the main sidecar syncs the whole vault.
#
# When NESTED_PARENT is set, VAULT_PATH must be an existing directory strictly
# inside NESTED_PARENT. Otherwise the nested client would cover the whole vault
# (an empty subpath) or a folder outside it, and two clients would sync the same
# files to different remotes. Fails closed with a reason. No-op when
# NESTED_PARENT is unset, so the main sidecar is unaffected.
#
set -euo pipefail

[ -n "${NESTED_PARENT:-}" ] || exit 0

VAULT_PATH="${VAULT_PATH:-/vault}"
if [ ! -d "$VAULT_PATH" ]; then
  echo ">> nested-guard: $VAULT_PATH does not exist. Create the folder in the vault first." >&2
  exit 1
fi
parent="$(realpath "$NESTED_PARENT")"
child="$(realpath "$VAULT_PATH")"
case "$child" in
  "$parent"/?*) exit 0 ;;
esac
echo ">> nested-guard: VAULT_PATH ($child) must be a folder inside NESTED_PARENT ($parent)." >&2
echo ">> Set NESTED_SYNC_SUBPATH to the folder's path relative to the vault root." >&2
exit 1
