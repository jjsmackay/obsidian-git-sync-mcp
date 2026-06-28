## ADDED Requirements

### Requirement: Push credential is configured via VAULT_GIT_TOKEN

The extension SHALL recognise `VAULT_GIT_TOKEN` as the configuration value that
holds the HTTPS push credential, following the existing `VAULT_GIT_*` convention.
When set, it SHALL be the credential used for authenticated git operations via the
env-reading credential helper; the extension SHALL NOT log or echo its value.

#### Scenario: Token is read from the environment

- **WHEN** the extension is enabled and `VAULT_GIT_TOKEN` is set
- **THEN** the configured token is made available to the worker's credential path
- **AND** the token value never appears in logs or error messages

### Requirement: Startup validation fails closed on a missing credential

`validate_gitsync()` SHALL fail closed at startup when the extension is enabled
with a push remote configured and the remote requires a credential that cannot be
resolved. Specifically, when the resolved remote URL uses HTTPS, carries no
embedded credential, and `VAULT_GIT_TOKEN` is unset or empty, the server SHALL
refuse to start and SHALL report that no push credential is configured, without
echoing the remote URL or any secret. An SSH remote, an HTTPS remote that embeds a
credential, or commit-only mode (no push remote) SHALL NOT require `VAULT_GIT_TOKEN`.

#### Scenario: HTTPS remote with no credential refuses to start

- **WHEN** the extension is enabled, the push remote resolves to a tokenless HTTPS
  URL, and `VAULT_GIT_TOKEN` is unset
- **THEN** `validate_gitsync()` fails
- **AND** the server refuses to start, reporting that no push credential is
  configured, without echoing the remote URL

#### Scenario: HTTPS remote with token passes

- **WHEN** the extension is enabled, the push remote resolves to a tokenless HTTPS
  URL, and `VAULT_GIT_TOKEN` is set
- **THEN** `validate_gitsync()` passes the credential check and the server starts

#### Scenario: SSH remote does not require a token

- **WHEN** the extension is enabled and the push remote resolves to an SSH URL
- **THEN** `validate_gitsync()` does not require `VAULT_GIT_TOKEN` and the
  credential check passes

#### Scenario: Commit-only mode does not require a token

- **WHEN** the extension is enabled with no push remote configured (commit-only)
- **THEN** `validate_gitsync()` does not require `VAULT_GIT_TOKEN`
