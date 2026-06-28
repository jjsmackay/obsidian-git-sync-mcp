# Design

## Context

The worker commits against an *existing* git working tree — it never runs `git init`
or `git clone`. Combined with the fail-closed `validate_gitsync()` (`config.py`), this
makes seeding the vault repo a hard precondition, not optional polish: an unseeded vault
with `VAULT_GIT_ENABLED=true` crash-loops the `mcp` container.

## Decisions

- **Vault location: a single bind mount at any host path.** Keep
  `${VAULT_HOST_PATH:-./vault}:${VAULT_PATH}`. "Flexible" means pointing
  `VAULT_HOST_PATH` at any host path; bootstrap is always a plain `git clone` on the
  host. Rejected as over-built: an auto-clone entrypoint, and a named-volume + compose
  override file.
- **Both credential mechanisms first-class:** token-in-https-URL *and* SSH deploy key.

## Changes

### Image (mcp) — enable SSH transport
Add `openssh-client` to the apt install. One line. Required for the SSH deploy-key path;
no effect on the token path. The `obsidian-sync` image is untouched (it runs `ob`, not
git).

### Compose — concrete, opt-in credential mount
On the `mcp` service, a ready-to-uncomment SSH deploy-key mount + `GIT_SSH_COMMAND`
(`StrictHostKeyChecking=accept-new`). The token-in-https-URL path needs no compose
change — the credential lives in the vault's `.git/config` on the bind-mounted tree.

### README — "Git repo bootstrap" section
Fail-closed gotcha up front (the container refuses to boot if the repo/remote is
missing), then: clone into `VAULT_HOST_PATH` → choose a credential (token-in-https-URL
recommended; or SSH deploy key) → set `VAULT_GIT_ENABLED=true` and deploy. Plus an
ordering note: clone the git tree first, then run the `ob` bootstrap against the same
`/vault`.

## Scope / risk

Config + docs only — no Python logic change, so no test change.

## Out of scope

- Auto-clone entrypoint (adds image complexity + a boot-time failure surface).
- Named-volume support for the vault and a compose override file.
- Any change to the worker's git logic or startup validation.
- Deployment-time wiring of a specific stack (a separate operational concern, not a repo
  artifact).
