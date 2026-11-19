#!/usr/bin/env bash
#
# Entry point for the obsidian-sync sidecar. Decides what to run:
#
#   * `bootstrap` arg, or BOOTSTRAP set   -> interactive bootstrap
#   * any other explicit command          -> run it verbatim (escape hatch, e.g.
#                                            `docker run ... <image> sh`)
#   * no command, sync configured         -> ob sync --continuous (normal mode)
#   * no command, NOT configured          -> print instructions, then poll for
#                                            config (every $SYNC_POLL_INTERVAL,
#                                            default 5s) so a `up -d` deploy does
#                                            NOT crash-loop; once you
#                                            `docker exec -it ... bootstrap`,
#                                            continuous sync auto-starts -- no
#                                            manual restart.
#
# Bootstrap is ALWAYS explicit (arg/env/exec); the poll loop auto-starts only
# *sync*, never bootstrap. We deliberately do not auto-start bootstrap on a
# detected TTY: compose's `tty: true` makes stdin a TTY even with nobody
# attached, so auto-on-TTY would hang at the `ob login` prompt forever.
#
set -euo pipefail
VAULT_PATH="${VAULT_PATH:-/vault}"
CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"
SYNC_POLL_INTERVAL="${SYNC_POLL_INTERVAL:-5}"

# Bootstrapped means sync-setup has run, which creates a per-vault directory
# under CONFIG_DIR/sync/. Login alone writes only auth_token, so checking for a
# non-empty CONFIG_DIR started sync mid-bootstrap (between `ob login` and
# `sync-setup`): `ob sync` exited "no sync configuration", the container
# restarted and the operator's interactive bootstrap session was killed.
is_bootstrapped() { [ -n "$(ls -A "$CONFIG_DIR/sync" 2>/dev/null)" ]; }

if [ "${1:-}" = "bootstrap" ]; then
  shift               # drop the 'bootstrap' token, forward the rest (e.g. --reset)
  exec bootstrap "$@"
elif [ -n "${BOOTSTRAP:-}" ]; then
  exec bootstrap
fi

# An explicit command was passed -> honour it (don't second-guess the operator).
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if is_bootstrapped; then
  exec ob sync --path "$VAULT_PATH" --continuous
fi

echo ">> obsidian-sync is NOT bootstrapped (no config in $CONFIG_DIR)."
echo ">> Run:  docker exec -it <container> bootstrap"
echo ">> Idling and polling every ${SYNC_POLL_INTERVAL}s; sync starts automatically once you do."

# Poll instead of idling forever: as soon as `bootstrap` writes config into
# CONFIG_DIR, start continuous sync ourselves -- no manual restart. We never
# auto-run bootstrap (the explicit-only / TTY caveat above still holds); we only
# auto-start *sync* once config exists.
while ! is_bootstrapped; do
  sleep "$SYNC_POLL_INTERVAL"
done
exec ob sync --path "$VAULT_PATH" --continuous
