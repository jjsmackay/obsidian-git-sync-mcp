## ADDED Requirements

### Requirement: Push heartbeat on successful sync

When a heartbeat URL is configured, the worker SHALL send a single GET to it
after a push succeeds, and SHALL NOT send it after a failed push or when no
remote is configured (commit-only mode). When no heartbeat URL is configured, no
heartbeat SHALL ever be sent.

#### Scenario: Successful push fires the heartbeat

- **WHEN** a push completes successfully and a heartbeat URL is configured
- **THEN** a single GET is sent to that URL

#### Scenario: Failed push does not fire the heartbeat

- **WHEN** a push fails
- **THEN** no heartbeat is sent

#### Scenario: Disabled by default

- **WHEN** no heartbeat URL is configured
- **THEN** no heartbeat is ever sent

### Requirement: Safe ping discipline

The heartbeat ping SHALL follow no redirects, read at most a small bounded
number of bytes of the response, use a short timeout, and never log the full URL
(only the host and the exception type), since the URL may be a capability URL
with a secret in its path. A ping failure SHALL be logged and swallowed and
SHALL NOT affect sync.

#### Scenario: A failing heartbeat never breaks sync

- **WHEN** the heartbeat endpoint is unreachable or errors
- **THEN** the failure is logged (host + error type only) and the worker
  continues normally

#### Scenario: Redirects are not followed

- **WHEN** the heartbeat URL responds with a redirect
- **THEN** the ping does not follow it

### Requirement: Heartbeat configuration is validated fail-closed

When `VAULT_GIT_HEARTBEAT_URL` is set, `validate_gitsync()` SHALL require it
to be an http(s) URL with a host, failing closed at startup otherwise. An empty
value disables the heartbeat and is always valid.

#### Scenario: Bad scheme refuses to start

- **WHEN** the extension is enabled and the heartbeat URL is not an http(s) URL
  with a host
- **THEN** `validate_gitsync()` raises and the server fails closed at startup

#### Scenario: Empty heartbeat URL is valid

- **WHEN** the heartbeat URL is empty
- **THEN** validation passes and no heartbeat is configured
