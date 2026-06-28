## ADDED Requirements

### Requirement: Image supports SSH deploy-key git transport

The mcp image SHALL include an SSH client so the git-sync worker can push over an
`ssh` remote when a deploy key is mounted. Git's SSH transport invokes an `ssh`
binary, which is only a Recommends of `git` and is therefore dropped by
`--no-install-recommends`; the image SHALL install it explicitly.

#### Scenario: ssh available in the image

- **WHEN** `ssh -V` is run inside the built mcp image
- **THEN** it reports an SSH client version (git's SSH transport dependency is present)

#### Scenario: Token path unaffected

- **WHEN** the vault uses a token-bearing https remote (no SSH)
- **THEN** pushing works without any SSH client involvement

### Requirement: Compose documents both push-credential mechanisms

`docker-compose.yml` SHALL document, opt-in (commented out by default), the two ways to
supply the worker's push credential without baking it into the image: a token-bearing
https remote (no mount needed; the token lives in the vault's `.git/config`) and an SSH
deploy-key mount paired with `GIT_SSH_COMMAND`.

#### Scenario: SSH deploy-key path is documented and ready to enable

- **WHEN** the `mcp` service definition is inspected
- **THEN** it carries a commented, ready-to-uncomment SSH deploy-key volume mount and a
  `GIT_SSH_COMMAND` environment entry

#### Scenario: Token path requires no compose change

- **WHEN** the token-in-https-URL mechanism is used
- **THEN** the compose file documents that no mount is required (the credential lives in
  the vault working tree's `.git/config`)
