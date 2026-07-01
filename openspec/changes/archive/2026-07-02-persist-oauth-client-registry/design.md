## Context

The upstream server writes its dynamically-registered OAuth client registry to
`OAUTH_CLIENTS_PATH` (default: under the container user's home) with 0600 perms
via `oauth._save_clients`. The registry is the DCR `client_id` → secret map that
lets an already-connected MCP client re-present its `client_id` on reconnect. The
mcp service only persists the vault volume, so the registry sits on the
container's ephemeral layer and is destroyed on every redeploy — after which
connected clients replay a now-unknown `client_id` and get `invalid_client`.

A survey of the mcp container's writable state confirms the registry is the only
gap: the frontmatter index is an in-memory dict rebuilt from the vault at boot,
soft-deletes and `.obsidian/` and `.git/` all live under the vault volume, and
git credentials are read from the environment (`VAULT_GIT_TOKEN`) with nothing on
disk to persist.

The mcp image runs as the non-root uid 10001, and a fresh Docker named volume
mounts root-owned — the same ownership problem the vault volume and the sidecar
config volume already hit.

## Goals / Non-Goals

**Goals:**
- Registered OAuth clients survive a redeploy (no more `invalid_client`).
- Do it with configuration only — no upstream/Python code change.
- Keep the per-client secrets off the git-pushed vault tree.
- Make the fresh-volume ownership case work without a manual host chown.

**Non-Goals:**
- Changing the OAuth model, the static-credential login gate, or the fact that
  the issued access token is `VAULT_MCP_TOKEN`.
- Persisting the frontmatter index (derived cache; rebuilds at boot).
- The deferred `VAULT_GIT_TOKEN` + tokenless-remote migration (separate change).

## Decisions

**Dedicated `/data` volume, not the vault volume.** The registry holds per-client
secrets. The git-sync worker sweeps the vault tree and pushes it to the vault
remote, so anything under `VAULT_PATH` (including `.trash/`) risks being
committed and published. A separate single-purpose volume keeps the secret file
structurally out of the tree. Alternative considered — reuse the sidecar's
`config` volume (already 10001-owned, so writable immediately) — rejected: it
couples mcp state into the sidecar's volume and muddies ownership of each
volume's contents.

**Image pre-creates `/data` as uid 10001.** A fresh named volume is root-owned;
uid 10001 then cannot write and `os.open(tmp, ..., 0o600)` in `_save_clients`
fails. Because the worker logs-and-swallows and the registry writer is
best-effort, this fails *silently* — the connector still works until the next
redeploy, so the regression is invisible until it recurs. Pre-creating and
chowning the mount point in the image (Docker copies the image-side ownership
onto a fresh empty volume on first mount) is the fix the sidecar already uses for
its config dir. Alternative — a documented one-off host `chown` like the vault
seed step — rejected: the vault needs a seed container anyway (to clone the
repo), but `/data` starts empty, so there is no reason to require a manual step.

**Configure via `OAUTH_CLIENTS_PATH` in compose, keep the code default.** The
upstream default stays as-is; the deployment overrides it to
`/data/oauth_clients.json`. This keeps the change config-only and leaves a plain
`docker compose up` on a host bind-mount unaffected.

## Risks / Trade-offs

- **Silent-failure ownership bug** → the image-side `mkdir -p /data && chown`
  (and a spec scenario asserting it) is the mitigation; the whole point of the
  second requirement is to make this failure mode impossible rather than quiet.
- **Existing deployments already broke their registry** → this change does not
  recover lost registrations; the first client to authenticate after deploy
  re-registers and *that* registration is what survives thereafter. One final
  re-auth is expected on rollout.
- **Registry file holds secrets on a volume** → same 0600 file, just relocated;
  no new exposure versus the upstream default, and strictly better than the
  vault-tree alternative.
- **Rollback** → drop the volume + env line and rebuild; behaviour reverts to the
  ephemeral (pre-change) default with no data-loss consequence beyond another
  re-auth.

## Migration Plan

1. Ship the image (pre-created `/data`) and the compose change (volume +
   `OAUTH_CLIENTS_PATH`).
2. On the `sybsidian` stack: add the named volume and the env var, then redeploy.
3. Authenticate once; that registration now persists across subsequent redeploys.

## Open Questions

None.
