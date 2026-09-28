# Spec Delta

## MODIFIED Requirements

### Requirement: Worker failures never crash the server

Any git command failure in the worker — staging, commit, fetch, rebase, push —
SHALL be logged and swallowed; it SHALL NOT propagate out of the worker thread or
stop the MCP server. The worker SHALL continue processing subsequent events. No
git failure SHALL be silent: a command that fails without producing a log entry
is indistinguishable from a system with nothing to do, which hides a total
outage.

#### Scenario: A failed push does not stop the worker

- **WHEN** a push fails (e.g. the remote is unreachable)
- **THEN** the failure is logged, the worker keeps running, and a later push
  retries the accumulated commits

#### Scenario: A failed stage is logged

- **WHEN** staging fails during an `MCP_WRITE` or a `SYNC_SWEEP` — for example
  because the repository index cannot be written
- **THEN** the failure is logged with its exit code, naming which path it
  occurred in, and the worker keeps running

#### Scenario: A failed stage creates no commit

- **WHEN** staging fails
- **THEN** no commit is created from that cycle, and the worker does not treat
  the empty index as a successful no-op

## ADDED Requirements

### Requirement: The worker records whether its last cycle completed cleanly

The worker SHALL maintain an observable record of whether its most recent event
cycle completed without a git failure. A cycle in which staging or committing
failed SHALL mark the worker degraded; a subsequent cycle that completes without
a git failure SHALL clear it. This state exists so that a monitor can tell "there
was nothing to commit" apart from "committing is broken" — two situations that
are otherwise identical from outside the process, because both leave the index
empty and nothing pushed.

The record SHALL reflect the worker's own cycles only. It SHALL NOT be cleared by
anything other than a cycle that completed cleanly, so a degraded worker cannot
appear to recover merely because time has passed or because no events arrived.

#### Scenario: A failed stage marks the worker degraded

- **WHEN** a cycle's staging command fails
- **THEN** the worker is recorded as degraded

#### Scenario: A failed commit marks the worker degraded

- **WHEN** staging succeeds but the commit command fails
- **THEN** the worker is recorded as degraded

#### Scenario: A clean cycle clears the record

- **WHEN** a cycle completes with no git failure after a degraded cycle
- **THEN** the worker is no longer recorded as degraded

#### Scenario: An idle cycle does not clear a degraded record

- **WHEN** the worker is degraded and a cycle runs in which no git command is
  attempted because there was nothing to do
- **THEN** the worker remains recorded as degraded

#### Scenario: A healthy worker is not degraded

- **WHEN** the worker has processed only cycles in which every git command
  succeeded
- **THEN** it is not recorded as degraded
