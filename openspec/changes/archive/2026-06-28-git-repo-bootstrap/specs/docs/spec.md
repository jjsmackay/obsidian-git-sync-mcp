## ADDED Requirements

### Requirement: Git repo bootstrap is documented

The README SHALL document how to seed the vault git repo before enabling git sync,
including the fail-closed precondition and both push-credential mechanisms. The worker
commits against an existing tree and never clones, and startup is fail-closed, so the
docs must make seeding an explicit prerequisite.

#### Scenario: Fail-closed precondition is stated

- **WHEN** a reader consults the bootstrap section
- **THEN** it states that with `VAULT_GIT_ENABLED=true` the container refuses to boot if
  the vault is not a git working tree or the configured remote is missing, so the repo
  must be seeded first

#### Scenario: An operator can bootstrap the git repo from the README

- **WHEN** an operator follows the bootstrap section
- **THEN** it walks them through cloning the vault into `VAULT_HOST_PATH`, choosing a
  push credential (token-in-https-URL or SSH deploy key), and then enabling git sync

#### Scenario: Ordering with the obsidian-sync bootstrap is given

- **WHEN** both the git repo and the obsidian-sync sidecar need bootstrapping
- **THEN** the README states the git tree is established first, then the `ob` bootstrap
  runs against the same vault path
