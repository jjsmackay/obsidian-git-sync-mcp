## ADDED Requirements

### Requirement: Startup validation fails closed on an unresolvable committer identity

`validate_gitsync()` SHALL fail closed at startup when the extension is enabled and
git cannot resolve a committer identity. It SHALL probe identity through git itself,
using the same identity overrides the worker applies — `-c user.name=…` and/or
`-c user.email=…` from the configured `VAULT_GIT_GIT_AUTHOR_NAME`/
`VAULT_GIT_GIT_AUTHOR_EMAIL`, or none when those are unset — so the check sees the
identity a commit would use. When git reports no resolvable identity, the server
SHALL refuse to start and SHALL report a clear error naming
`VAULT_GIT_GIT_AUTHOR_NAME` and `VAULT_GIT_GIT_AUTHOR_EMAIL` as the remedy. When the
extension is disabled, the check SHALL NOT run.

#### Scenario: Configured env identity passes

- **WHEN** the extension is enabled and `VAULT_GIT_GIT_AUTHOR_NAME` and
  `VAULT_GIT_GIT_AUTHOR_EMAIL` are both set
- **THEN** `validate_gitsync()` resolves the identity via git and the server starts

#### Scenario: Host git identity passes

- **WHEN** the extension is enabled with no `VAULT_GIT_GIT_AUTHOR_*` set, but the
  host git config resolves both a name and an email
- **THEN** `validate_gitsync()` resolves the identity via git and the server starts

#### Scenario: No resolvable identity refuses to start

- **WHEN** the extension is enabled and neither `VAULT_GIT_GIT_AUTHOR_*` nor the
  host git config resolves a committer identity
- **THEN** `validate_gitsync()` fails
- **AND** the server refuses to start, reporting that no committer identity is
  resolvable and naming `VAULT_GIT_GIT_AUTHOR_NAME`/`VAULT_GIT_GIT_AUTHOR_EMAIL` as
  the remedy

#### Scenario: Disabled extension does not check identity

- **WHEN** the extension is disabled
- **THEN** `validate_gitsync()` performs no committer-identity check and does not
  raise, regardless of identity configuration
