## Why

There is no way to switch the `obsidian-sync` sidecar to a different Obsidian
account. `ob`'s credentials and per-vault sync state persist on the `config`
named volume, and `bootstrap` just re-runs `ob login` on top of whatever is
already there — so a fresh `ob login` layers onto the old account's state rather
than replacing it. The README documents a manual workaround (stop the container,
run a throwaway `alpine` to `rm -rf` the volume, run a one-off `bootstrap`, start
again) — fiddly, easy to get wrong, and it duplicates the path-wiping logic
outside the image where it can't be guarded.

## What Changes

- Add a `--reset` flag to `obsidian-sync/bootstrap.sh`. On `--reset` the script
  wipes the persisted `ob` config/state under `CONFIG_DIR` first, then falls
  through to the existing login → sync-setup → status flow — a clean account
  switch in one command.
- Because the wipe is destructive (it discards credentials and sync state),
  `--reset` prompts for an explicit `yes` confirmation before deleting anything.
- Define `CONFIG_DIR` in `bootstrap.sh` exactly as `entrypoint.sh` does
  (`${HOME:-/home/ob}/.config/obsidian-headless`) so the two stay consistent, and
  guard the path before wiping so it can never run against `/` or an empty value.
- Unknown flags exit non-zero with a one-line usage message; no args is the
  unchanged normal bootstrap.
- Update `obsidian-sync/README.md`: replace the manual stop/`alpine`/wipe recipe
  with `docker exec -it <c> bootstrap --reset`.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `obsidian-sync-sidecar`: add a requirement that `bootstrap` supports a
  destructive `--reset` flag which confirms, wipes the persisted config/state,
  then runs the normal bootstrap flow — enabling an in-place account switch.

## Impact

- **Bootstrap** (`obsidian-sync/bootstrap.sh`): new `--reset` arg parsing, a
  guarded `CONFIG_DIR` wipe behind a confirmation prompt, and a usage message for
  unknown flags. The login/sync-setup/status flow is unchanged.
- **Docs** (`obsidian-sync/README.md`): the re-bootstrap section becomes a single
  `bootstrap --reset` command.
- No change to the Dockerfile, Compose, or the git-sync side. `entrypoint.sh` is
  touched only if `--reset` forwarding is clean, otherwise `--reset` is invoked
  directly via `docker exec -it <c> bootstrap --reset`.
