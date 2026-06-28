## Context

`obsidian-sync/bootstrap.sh` is baked into the image at `/usr/local/bin/bootstrap`
and run by an operator inside the container (`docker exec -it <c> bootstrap`). It
runs under `set -euo pipefail`, defines only `VAULT_PATH`, and walks `ob login` →
`ob sync-list-remote` → read vault id → read hidden e2e password → `ob sync-setup`
→ `ob sync-status`. It takes no arguments today.

`obsidian-sync/entrypoint.sh` is the container entry point. Its first branch is
`if [ "${1:-}" = "bootstrap" ] || [ -n "${BOOTSTRAP:-}" ]; then exec bootstrap; fi`
— note it `exec`s `bootstrap` with **no arguments**, so an arg passed to the
entry point is dropped. The entry point also defines
`CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"` (`entrypoint.sh:24`),
where `ob` stores credentials and per-vault `state.db`.

The problem: `ob`'s config/state is sticky on the `config` named volume, and
`bootstrap` re-runs `ob login` on top of it. There is no supported way to switch
accounts; the README documents a manual stop/`alpine rm -rf`/one-off-run recipe
that re-implements the wipe outside the image, unguarded.

`ob` exposes `logout` and `sync-unlink` subcommands, but (per the README's own
note) `ob logout` alone won't necessarily clear a configured vault's sync link —
a clean directory wipe is the reliable reset. Operators bootstrap by running
`/usr/local/bin/bootstrap` directly, so the flag is parsed by `bootstrap.sh`
itself.

## Goals / Non-Goals

**Goals:**
- One command switches the sidecar to a different Obsidian account:
  `docker exec -it <c> bootstrap --reset`.
- The destructive wipe is confirmed explicitly before anything is deleted.
- After the wipe, fall straight through to the existing login/sync-setup flow —
  no duplicated bootstrap logic.
- Keep `CONFIG_DIR` defined identically to `entrypoint.sh`.
- Keep `set -euo pipefail` correctness and the hidden e2e password read.
- Unknown flags fail fast with a short usage message.

**Non-Goals:**
- Unattended/forced reset. `--reset` always confirms interactively; `ob login`
  already requires an attended TTY (account + MFA), so a non-interactive reset
  buys nothing.
- Selectively unlinking a single vault while keeping the account. The reset wipes
  all of `CONFIG_DIR`; partial state surgery is out of scope.
- Changing the normal (no-arg) bootstrap behaviour.

## Decisions

### Parse `--reset` in `bootstrap.sh`; everything else is an error

A small arg parse near the top: no args → normal bootstrap; `--reset` → set a
flag and continue; anything else → print `usage: bootstrap [--reset]` to stderr
and `exit 2`. Keeping the parser in `bootstrap.sh` (not the entry point) means the
flag works the same whether invoked via `docker exec … bootstrap --reset`, a
one-off `run`, or forwarded by the entry point.

### Define `CONFIG_DIR` exactly as `entrypoint.sh` does

Add `CONFIG_DIR="${HOME:-/home/ob}/.config/obsidian-headless"` alongside
`VAULT_PATH`. Same expression as `entrypoint.sh:24`, so `is_bootstrapped`'s notion
of "where config lives" and the reset's notion of "what to wipe" can never drift.

### Confirm, then wipe the directory *contents* (guarded), not the directory

On `--reset`, before deleting anything: prompt `read -rp` for an explicit `yes`;
any other answer aborts with a message and `exit 0` (no harm done). On
confirmation, guard the path — refuse to proceed unless `CONFIG_DIR` is non-empty
as a string, is not `/`, and exists as a directory — then remove its contents
(`rm -rf -- "$CONFIG_DIR"/* "$CONFIG_DIR"/.[!.]* "$CONFIG_DIR"/..?*` under a
subshell with nullglob/dotglob, or an equivalent safe glob), leaving the
volume-mounted directory itself in place. Wiping contents (not the mount point)
keeps the named-volume mount intact and mirrors the README's existing
`rm -rf /c/* /c/.[!.]*` recipe, just guarded and inside the image.

Alternative considered: `ob logout` / `ob sync-unlink`. Rejected as the sole
mechanism — the README already records that `ob logout` won't reliably clear a
configured vault's sync link, so a directory wipe is the dependable reset. We can
mention `ob` subcommands but must not rely on them.

### Fall through to the existing flow — no duplication

After the wipe, the script simply continues into the unchanged `ob login` →
`sync-list-remote` → `sync-setup` → `sync-status` sequence. `--reset` is a
*prefix* action, not a separate code path, so there is exactly one bootstrap flow.

### Entry point forwards args (clean, one-word change)

Change `exec bootstrap` to `exec bootstrap "$@"` in `entrypoint.sh`'s first
branch is *not* sufficient on its own, because `$1` is the literal `bootstrap`
token. Instead `shift` is unsafe when the branch is also entered via `BOOTSTRAP`
env (no positional). The clean, minimal change: when entered via the `bootstrap`
arg, forward the *remaining* args. We do this by guarding the shift:
`if [ "${1:-}" = "bootstrap" ]; then shift; exec bootstrap "$@"; elif [ -n "${BOOTSTRAP:-}" ]; then exec bootstrap; fi`. This lets
`docker run … obsidian-sync bootstrap --reset` and
`docker compose run --rm obsidian-sync bootstrap --reset` forward `--reset`, while
the `BOOTSTRAP` env path (no positional args to forward) is unchanged. The common
operator path — `docker exec -it <c> bootstrap --reset` — bypasses the entry point
entirely and already works regardless.

## Risks / Trade-offs

- **Accidental data loss** → The wipe is gated behind an explicit `yes` prompt and
  a path guard; `ob login` reauth is required afterwards anyway, so a mistaken
  reset is recoverable by re-bootstrapping the original account.
- **`rm -rf` footgun** → Guard `CONFIG_DIR` (non-empty string, `!= /`, is a
  directory) before any removal, and only ever target globs *under* it with `--`.
  Never `rm -rf "$CONFIG_DIR"` unquoted or bare.
- **`set -e` aborting on a no-match glob** → Do the removal in a subshell with
  `shopt -s nullglob dotglob` (or a `find … -mindepth 1 -delete`) so an
  already-empty dir doesn't error; the confirmation read sits outside any
  condition that `errexit` would trip.
- **Entry-point arg forwarding regressions** → The `BOOTSTRAP` env branch keeps
  its no-arg `exec bootstrap`; only the explicit-`bootstrap`-arg branch shifts and
  forwards, so the auto-start / passthrough / continuous-sync branches are
  untouched.

## Migration Plan

Pure script behaviour change in a rebuilt image; no data or config migration.
Rollback is reverting the script. The manual stop/`alpine`/wipe recipe still works
for anyone on an older image; the README simply points new operators at
`bootstrap --reset`.
