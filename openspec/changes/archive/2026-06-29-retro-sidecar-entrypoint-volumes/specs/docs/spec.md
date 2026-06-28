## ADDED Requirements

### Requirement: Worker commit identity is documented

The README SHALL document that the git-sync worker needs a commit identity, because
git refuses to commit without one and every sweep commit otherwise fails (e.g.
`git-worker sweep commit failed (rc=128)`). It SHALL state the two ways to supply it:
set `VAULT_GIT_GIT_AUTHOR_NAME` and `VAULT_GIT_GIT_AUTHOR_EMAIL` in `.env`, or
configure `user.name`/`user.email` in the vault's own git config.

#### Scenario: Commit identity requirement is stated

- **WHEN** a reader consults the bootstrap docs
- **THEN** it states the worker needs a commit identity and gives both ways to set it
  (the `VAULT_GIT_GIT_AUTHOR_*` env vars or the vault's git config)

### Requirement: Bootstrap ordering and re-bootstrap are documented

The README SHALL document the ordering between establishing the git tree and the
sidecar's `ob` bootstrap, and SHALL document how to re-bootstrap the sidecar to switch
accounts. The git tree (working tree + remote) SHALL be established first, then the
one-time `ob` bootstrap runs against the same vault path; the push credential SHALL be
set before the sidecar first syncs content down. Re-bootstrapping SHALL be documented
as `bootstrap --reset`, which confirms before discarding the stored login and sync
state and then falls through to the normal login → sync-setup → status flow, with
continuous sync auto-starting for the new account afterwards (no manual restart).

#### Scenario: Bootstrap ordering is documented

- **WHEN** both the git tree and the sidecar need bootstrapping
- **THEN** the README states the git tree is established first, then the `ob` bootstrap
  runs against the same vault path, with the push credential set before the first sync

#### Scenario: Re-bootstrap path is documented

- **WHEN** an operator needs to switch the sidecar to a different account
- **THEN** the docs describe `bootstrap --reset` wiping the stored config after
  confirmation and re-running the normal bootstrap flow, with sync auto-starting after
