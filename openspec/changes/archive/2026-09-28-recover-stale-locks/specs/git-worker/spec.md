# Spec Delta

## ADDED Requirements

### Requirement: Stale repository locks are cleared at startup

When git sync is enabled, the extension SHALL look for lock files left in the
repository's git directory at startup, before the worker runs any git command,
and SHALL remove each one it judges stale. The locks covered are the index lock,
the HEAD, config and packed-refs locks, and any ref lock under the refs
directory. The index lock alone is not enough, because an interrupted ref update
leaves a ref lock that blocks sync just as completely.

A lock SHALL be judged stale only when both hold: no git process is running, and
the lock is older than a fixed threshold no shorter than the worker's git command
timeout. If either test fails, or if it cannot be determined whether a git
process is running, the lock SHALL be left in place.

The sweep SHALL NOT refuse or delay startup: finding, removing or failing to
remove a lock never stops the MCP server from serving. A lock left in place is
reported at runtime through the degraded state, not by a failed boot.

#### Scenario: An orphaned index lock is cleared

- **WHEN** the extension starts with git sync enabled, the index lock exists and
  is older than the threshold, and no git process is running
- **THEN** the lock is removed before the worker's first git command, and the
  first sweep stages and commits the changes that were blocked behind it

#### Scenario: A ref lock is cleared as well as the index lock

- **WHEN** the extension starts and a stale lock exists for a branch ref
- **THEN** that ref lock is removed on the same terms as the index lock

#### Scenario: A young lock is left in place

- **WHEN** the extension starts and a lock exists that is younger than the
  threshold
- **THEN** the lock is not removed, and a warning names it and its age

#### Scenario: A lock is left in place while git is running

- **WHEN** the extension starts and a git process is running
- **THEN** no lock is removed, whatever its age, and a warning says so

#### Scenario: Startup proceeds whatever the sweep finds

- **WHEN** the sweep cannot remove a lock, cannot tell whether git is running, or
  fails outright
- **THEN** the failure is logged, and the MCP server starts and serves normally

#### Scenario: Disabled git sync touches no locks

- **WHEN** the extension starts with git sync disabled
- **THEN** no lock is inspected or removed

### Requirement: Clearing a lock is always logged loudly

Every lock the startup sweep removes SHALL be logged at warning, naming the lock
file and its age. A removed lock is evidence that a git command was interrupted,
often by something outside the process such as a host freeze, and a silent
recovery would erase the only trace of it.

#### Scenario: A cleared lock produces a warning

- **WHEN** the startup sweep removes a lock
- **THEN** exactly one warning is logged for it, giving the lock's path relative
  to the git directory and its age

#### Scenario: A clean repository logs no warning

- **WHEN** the extension starts and no lock files are present
- **THEN** the sweep logs nothing at warning

### Requirement: Locks are never cleared while the worker is running

The worker SHALL NOT remove any lock file at runtime. When a staging or commit
failure marks the worker degraded and a lock file is present in the git
directory, the warning for that failure SHALL name the lock and its age, so a
reader knows the likely cause without inspecting the repository.

#### Scenario: A runtime stage failure names the blocking lock

- **WHEN** staging fails at runtime while the index lock is present
- **THEN** the warning names the index lock and its age, and the lock is left in
  place

#### Scenario: A runtime failure without a lock is reported as before

- **WHEN** staging or committing fails at runtime and no lock file is present
- **THEN** the warning reports the exit code as it does today and names no lock
