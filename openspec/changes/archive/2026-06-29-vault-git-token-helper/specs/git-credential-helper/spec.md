## ADDED Requirements

### Requirement: Push credential is supplied from the environment at invocation time

The system SHALL provide a git credential helper that reads the push credential
from the `VAULT_GIT_TOKEN` environment variable and emits it over git's
credential-helper protocol when git requests credentials for an HTTPS remote. The
token value SHALL NOT be written to `.git/config` and SHALL NOT appear in any
git command's argument vector. The helper SHALL be the credential source for the
worker's authenticated git operations; the operator supplies the token through
one environment variable only.

#### Scenario: Helper emits credentials from the environment

- **WHEN** git invokes the helper with the `get` action for an HTTPS remote and
  `VAULT_GIT_TOKEN` is set
- **THEN** the helper writes a `username` and a `password` field to stdout in the
  credential-helper format, with the token as the password
- **AND** the token value is read only from the process environment

#### Scenario: Token never persisted or exposed on the command line

- **WHEN** the worker performs authenticated git operations with a token configured
- **THEN** the token value is absent from `.git/config`
- **AND** the token value is absent from every git argument vector (only the
  helper's name or path, and the credential-protocol fields it prints, are used)

#### Scenario: Missing token yields no credential

- **WHEN** git invokes the helper with the `get` action and `VAULT_GIT_TOKEN` is
  unset or empty
- **THEN** the helper outputs no credential fields and exits without error,
  letting git fall through to its normal credential resolution

#### Scenario: Store and erase actions are no-ops

- **WHEN** git invokes the helper with the `store` or `erase` action
- **THEN** the helper does nothing and exits zero, so git never caches or deletes
  the env-sourced token

### Requirement: Credential helper is wired into authenticated git operations

When `VAULT_GIT_TOKEN` is set, the worker SHALL configure its network git
operations (fetch and push) to use the env-reading credential helper, and SHALL
suppress any inherited system or global credential helper so only the env helper
is consulted. Operations that do not contact the remote SHALL be unaffected.

#### Scenario: Network operations use the env helper

- **WHEN** a fetch or push runs with `VAULT_GIT_TOKEN` set
- **THEN** the git invocation is configured to use the env-reading credential
  helper for that operation
- **AND** any inherited credential helper is cleared for that invocation

#### Scenario: No token configured leaves git invocation unchanged

- **WHEN** `VAULT_GIT_TOKEN` is unset
- **THEN** the worker does not add credential-helper configuration to its git
  operations, preserving today's behaviour (credentials resolved by git as before)

### Requirement: Tokenless remote URL is the supported credential path

With `VAULT_GIT_TOKEN` set, the credential helper SHALL supply credentials for an
HTTPS remote whose URL carries no embedded credentials. A remote URL that already
embeds a credential SHALL continue to work for backward compatibility, but the
env-supplied token SHALL be the documented and recommended path.

#### Scenario: Tokenless HTTPS remote authenticates via the helper

- **WHEN** the remote URL is `https://<host>/<owner>/<repo>.git` (no embedded
  credential) and `VAULT_GIT_TOKEN` is set
- **THEN** fetch and push authenticate using the credential supplied by the helper

#### Scenario: Embedded-credential remote still works

- **WHEN** the remote URL embeds a credential and `VAULT_GIT_TOKEN` is unset
- **THEN** fetch and push continue to authenticate using the embedded credential,
  unchanged from prior behaviour
