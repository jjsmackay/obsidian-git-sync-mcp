## Context

`obsidian-sync/entrypoint.sh` runs under `set -euo pipefail` and decides what to
run at container start (`entrypoint.sh:26–42`). Four branches, in order:

1. `bootstrap` arg / `BOOTSTRAP` env → `exec bootstrap` (interactive, explicit).
2. Any explicit command → `exec "$@"` (verbatim escape hatch).
3. `is_bootstrapped` (config dir non-empty) → `exec ob sync … --continuous`.
4. Otherwise → print instructions + `exec sleep infinity`.

`is_bootstrapped()` (`entrypoint.sh:24`) tests whether `CONFIG_DIR`
(`~/.config/obsidian-headless`) is non-empty; the image pre-creates it empty, so
"empty" reliably means "not yet bootstrapped".

The problem is branch 4. After an operator runs `docker exec -it <c> bootstrap`
against the idle container, config lands in `CONFIG_DIR`, but the running PID 1 is
`sleep infinity`, so sync never starts until the container is restarted. The
README currently documents that manual-restart step as a caveat, and HANDOFF
flags it as a known sharp edge (a redeploy that sees no config change may not
recreate the container).

Bootstrap is deliberately explicit-only: compose's `tty: true` makes stdin a TTY
even with nobody attached, so any "auto-on-TTY" bootstrap would hang at the
`ob login` prompt forever (header comment, `entrypoint.sh:13–15`).

## Goals / Non-Goals

**Goals:**
- The idle, un-bootstrapped sidecar begins continuous sync on its own once config
  appears — no manual restart.
- Print the bootstrap instructions exactly once, then idle quietly between checks.
- Poll interval overridable via an env var, with a sane default (5s).
- Preserve the three other branches byte-for-byte in behaviour.
- Keep `set -euo pipefail` correctness.

**Non-Goals:**
- Auto-running `bootstrap`. We only auto-start *sync* after config exists; the
  explicit-only bootstrap contract and its TTY rationale are unchanged.
- Watching for config changes via inotify or similar — a simple sleep-poll is
  sufficient and dependency-free for a slim container.
- Detecting a *partial* bootstrap (e.g. login done, sync-setup not). `is_bootstrapped`
  is a non-empty-dir heuristic, same as today; sync-setup writes the per-vault
  state that makes the dir non-empty, and a half-written config is an operator
  error out of scope here.

## Decisions

### Replace `exec sleep infinity` with a sleep-poll loop

Branch 4 becomes: print the instructions once (outside the loop), then
`while ! is_bootstrapped; do sleep "$interval"; done`, then
`exec ob sync --path "$VAULT_PATH" --continuous` — the exact command branch 3
uses. The `while`/`sleep`/`exec` shape keeps PID 1 responsive to signals between
sleeps and hands off to `ob` with `exec` (no lingering shell), matching the
existing branches.

Alternative considered: `inotifywait` on `CONFIG_DIR`. Rejected — it adds a
package to a slim image for no real gain over a 5s poll; bootstrap is a
human-paced one-off, so latency of a few seconds is irrelevant.

### Poll interval via an env var with a 5s default

Read `SYNC_POLL_INTERVAL` with a default of `5` (seconds), set near the other
config defaults at the top of the script (`SYNC_POLL_INTERVAL="${SYNC_POLL_INTERVAL:-5}"`).
The name mirrors the file's existing `VAULT_PATH` style and is sidecar-scoped, so
it won't collide with the `VAULT_GIT_*` config namespace on the mcp side.

Alternative considered: hard-coding 5s. Rejected — an env override is one line
under `set -u` and lets an operator tune polling without rebuilding the image, as
the design steer requested.

### Keep `is_bootstrapped` and the sync command as-is

The loop reuses the existing `is_bootstrapped` function and the branch-3 command
verbatim, so there is exactly one definition of "bootstrapped" and one sync
invocation. No new helper, no duplicated `ob sync` string semantics.

## Risks / Trade-offs

- **Busy-printing or log spam** → Print the instruction block once *before* the
  loop, not inside it; the loop body is only `sleep`. Quiet idle, same as today.
- **`set -e` aborting the loop** → `while ! is_bootstrapped; do …` puts the
  command in a condition list, where a non-zero exit is expected and does not trip
  `errexit`. `is_bootstrapped` already uses `ls … 2>/dev/null` and a `[ -n … ]`
  test, both safe under `-euo pipefail`.
- **Signal handling during sleep** → `sleep` is interruptible; an external `docker
  stop` (SIGTERM) terminates the shell as it does today with `sleep infinity`. No
  trap is added; behaviour on stop is unchanged.
- **Partial/aborted bootstrap leaving a non-empty dir** → Same exposure as the
  current branch-3 start path (any non-empty dir is treated as bootstrapped); not
  a regression, and out of scope (see Non-Goals).

## Migration Plan

Pure entry-point behaviour change in a rebuilt image; no data or config
migration. Rollback is reverting the script. Operators who previously restarted
after bootstrap can simply stop doing so; an explicit restart still works and is
harmless.
