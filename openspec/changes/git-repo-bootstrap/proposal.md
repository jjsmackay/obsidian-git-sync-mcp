## Why

The deployment docs covered the obsidian-sync sidecar bootstrap but never stepped
through getting a git working tree and a push credential into the vault. The README
only *asserted* "the vault must be a git working tree" and gestured at credentials in
`docker-compose.yml` comments. This matters more than it reads: startup is
**fail-closed** — with `VAULT_GIT_ENABLED=true`, `validate_gitsync()` refuses to boot
if `VAULT_PATH` is not a git working tree or if `VAULT_GIT_REMOTE` names a remote the
tree does not have. So an unseeded vault crash-loops the `mcp` container.

A secondary gap: the image installed only `git ca-certificates` with
`--no-install-recommends`. Git's SSH transport needs an `ssh` binary on PATH, and
`openssh-client` is only a *recommend* — so the SSH deploy-key credential option
silently failed in the built image. Only the token-in-https-URL path worked.

## What Changes

- **Dockerfile (mcp):** add `openssh-client` to the apt install so git's SSH transport
  works (the deploy-key credential path). No effect on the token path.
- **docker-compose.yml:** replace the prose credential comments on the `mcp` service
  with a concrete, opt-in SSH deploy-key mount + `GIT_SSH_COMMAND` block, and document
  that the token-in-https-URL path needs no mount (the credential lives in the vault's
  `.git/config`).
- **README:** add a "Git repo bootstrap" section — the fail-closed gotcha up front,
  then clone → choose a credential (token-in-https-URL recommended, or SSH deploy key)
  → enable git sync, plus an ordering note versus the obsidian-sync bootstrap.

## Capabilities

### Modified Capabilities
- `container-deployment`: the image now supports SSH-key git transport, and the compose
  push-credential surface is concrete and opt-in (both mechanisms documented).
- `docs`: the README documents the git-repo bootstrap and both credential mechanisms,
  including the fail-closed precondition.

### New Capabilities
<!-- None. This completes the deployment story for an existing capability. -->

## Impact

- Files: `Dockerfile`, `docker-compose.yml`, `README.md`.
- No Python logic change; no test change (102 tests unaffected).
- Operational: the vault must be seeded (clone + credential) **before** enabling git
  sync, or the container fails closed. Both credential mechanisms now work — SSH needs
  the `openssh-client` this change adds to the image.
