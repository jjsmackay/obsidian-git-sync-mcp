# Spec Delta

## MODIFIED Requirements

### Requirement: Push heartbeat on successful sync

When a heartbeat URL is configured, the worker SHALL send a single GET to it at
the end of any push cycle that leaves nothing owed to the remote — either
because a push has just succeeded, or because there was nothing to push — and
SHALL NOT send it while commits remain unpushed, while the worker is recorded as
degraded (see the `git-worker` capability), nor when no remote is configured
(commit-only mode). When no heartbeat URL is configured, no heartbeat SHALL ever
be sent.

A beat therefore asserts three things together: the worker is running, its last
cycle did real work without a git failure, and the remote is up to date. Silence
means one of: the worker is dead, it cannot stage or commit, or commits it has
made cannot be pushed.

All three terms are load-bearing. Without the degraded term, a worker whose
staging fails silently presents as an idle worker with nothing to push — the
index stays empty, nothing is owed to the remote, and the beat would continue
throughout a total outage. That is not hypothetical: it is the shape of a real
three-and-a-half-day outage. With all three, a vault nobody edits overnight keeps
beating, while any break in the commit-to-remote path goes quiet.

#### Scenario: Successful push fires the heartbeat

- **WHEN** a push completes successfully and a heartbeat URL is configured
- **THEN** a single GET is sent to that URL

#### Scenario: An idle worker with nothing to push still beats

- **WHEN** a push cycle runs, a heartbeat URL and a remote are configured, the
  worker is not degraded, and there is nothing unpushed
- **THEN** a heartbeat is sent, because the remote is up to date

#### Scenario: A degraded worker does not beat

- **WHEN** the worker is recorded as degraded — for example because staging is
  failing, so nothing reaches the index and nothing is owed to the remote
- **THEN** no heartbeat is sent, and none is sent until a cycle completes
  without a git failure

#### Scenario: Failed push does not fire the heartbeat

- **WHEN** a push fails
- **THEN** no heartbeat is sent

#### Scenario: Unpushed commits keep suppressing the heartbeat

- **WHEN** a cycle leaves commits unpushed
- **THEN** no heartbeat is sent on that cycle or any subsequent cycle until the
  commits reach the remote

#### Scenario: Commit-only mode never beats

- **WHEN** no remote is configured
- **THEN** no heartbeat is ever sent, whatever the heartbeat URL is set to

#### Scenario: Disabled by default

- **WHEN** no heartbeat URL is configured
- **THEN** no heartbeat is ever sent

### Requirement: Heartbeat configuration is validated fail-closed

When `VAULT_GIT_HEARTBEAT_URL` is set, `validate_gitsync()` SHALL require it
to be an http(s) URL with a host, failing closed at startup otherwise. An empty
value disables the heartbeat and is always valid. `VAULT_GIT_HEARTBEAT_INTERVAL`
SHALL be required to parse as a positive integer number of seconds, failing
closed at startup otherwise, so a typo cannot silently collapse the cadence
floor or flood the monitor.

#### Scenario: Bad scheme refuses to start

- **WHEN** the extension is enabled and the heartbeat URL is not an http(s) URL
  with a host
- **THEN** `validate_gitsync()` raises and the server fails closed at startup

#### Scenario: Empty heartbeat URL is valid

- **WHEN** the heartbeat URL is empty
- **THEN** validation passes and no heartbeat is configured

#### Scenario: Non-positive or unparseable interval refuses to start

- **WHEN** the extension is enabled and the heartbeat interval is not a positive
  integer
- **THEN** `validate_gitsync()` raises and the server fails closed at startup

## ADDED Requirements

### Requirement: Heartbeat cadence has a configurable floor

The worker SHALL NOT send heartbeats more often than a configured minimum
interval, which SHALL default to 60 seconds and SHALL be overridable via
`VAULT_GIT_HEARTBEAT_INTERVAL`. The floor is required because an idle worker
evaluates its push window every debounce period, which is far more often than a
monitor needs, and a beat carries no information a recent beat has not already
carried. The floor SHALL NOT delay the first eligible beat, and SHALL NOT cause
a beat to be sent on behalf of a cycle that was not itself eligible.

#### Scenario: Rapid eligible cycles collapse to one beat

- **WHEN** several push cycles complete with nothing owed to the remote within
  one interval
- **THEN** exactly one heartbeat is sent for that interval

#### Scenario: The first eligible cycle beats immediately

- **WHEN** the worker's first eligible push cycle completes after startup
- **THEN** a heartbeat is sent without waiting out an interval

#### Scenario: Override is honoured

- **WHEN** the interval variable is set to a value other than the default
- **THEN** that value is used as the minimum spacing between heartbeats

#### Scenario: A suppressed cycle does not beat later by accident

- **WHEN** an interval elapses in which every push cycle left commits unpushed
- **THEN** no heartbeat is sent for that interval
