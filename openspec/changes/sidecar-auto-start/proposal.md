## Why

When the `obsidian-sync` sidecar starts un-bootstrapped, its entry point prints
instructions and `exec sleep infinity`. After an operator runs
`docker exec -it <c> bootstrap` and writes the config into the persisted volume,
nothing happens — the running process is still `sleep infinity`, so sync only
begins after a manual container restart. The entry point "decides only at
container start" is a known sharp edge: an orchestrator redeploy that sees no
config change may not recreate the container, so the operator has to remember to
restart it by hand.

## What Changes

- Replace the terminal `exec sleep infinity` idle with a poll loop: print the
  bootstrap instructions once, then sleep a short interval and re-check
  `is_bootstrapped`. As soon as config appears in `CONFIG_DIR`, the entry point
  `exec`s `ob sync --path "$VAULT_PATH" --continuous` itself — no manual restart.
- Make the poll interval overridable via an env var (default 5 seconds) so the
  behaviour is tunable without rebuilding the image.
- Preserve every existing branch unchanged: explicit `bootstrap` arg / `BOOTSTRAP`
  env, explicit passthrough command, and already-bootstrapped → continuous sync.
- Keep bootstrap strictly explicit. The loop auto-starts *sync* only once config
  exists; it never auto-runs `bootstrap` (the TTY caveat in the header comment
  still holds — auto-on-TTY would hang at the `ob login` prompt).
- Update the README so the bootstrap flow no longer instructs a manual restart.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `obsidian-sync-sidecar`: add a requirement that the idle (un-bootstrapped)
  sidecar polls for config and auto-starts continuous sync once bootstrapped,
  removing the manual-restart step. Bootstrap remains explicit-only.

## Impact

- **Entry point** (`obsidian-sync/entrypoint.sh`): the un-bootstrapped branch
  becomes a poll loop; a new poll-interval env var with a 5s default. The three
  existing branches are untouched.
- **Docs** (`obsidian-sync/README.md`): drop the "restart it after bootstrap"
  caveat; describe the auto-start.
- No change to `bootstrap.sh`, the Dockerfile, Compose, or the git-sync side.
