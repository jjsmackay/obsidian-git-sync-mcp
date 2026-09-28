# git-worker Specification

## Purpose
TBD - created by archiving change git-worker. Update Purpose after archive.

## Requirements

### Requirement: Single git-worker consumer thread

When the extension is enabled, exactly one daemon worker thread SHALL drain the
event queue and perform all git operations. No other thread SHALL invoke git.
The worker SHALL start after the index is watching (`after_indexes_start`) and
SHALL stop on `shutdown`.

#### Scenario: One worker drains the queue

- **WHEN** the enabled extension has started
- **THEN** a single worker thread is running and consuming events from the queue

#### Scenario: Disabled starts no worker

- **WHEN** the extension is disabled
- **THEN** no worker thread is started and no git command is run

### Requirement: MCP writes become provenance-tagged commits

For an `MCP_WRITE` event, the worker SHALL stage the event's paths and, if
anything is staged, commit with a message `mcp: <operation> <paths>` — the single
path, or the first three followed by `(+N more)` when there are more than three.
When staging produces no change, the worker SHALL make no commit.

#### Scenario: Single-path MCP write

- **WHEN** an `MCP_WRITE` event for operation "updated" on `notes/a.md` is processed
  and that file has on-disk changes
- **THEN** a commit is created with message `mcp: updated notes/a.md`

#### Scenario: Many-path MCP write is summarised

- **WHEN** an `MCP_WRITE` event carries more than three paths
- **THEN** the commit message lists the first three paths and `(+N more)`

#### Scenario: No staged change makes no commit

- **WHEN** an `MCP_WRITE` event is processed but nothing is staged (already committed)
- **THEN** no commit is created

### Requirement: Sweeps commit out-of-band changes

For a `SYNC_SWEEP` event, the worker SHALL `git add -A` and, if the working tree
is dirty, commit with a message `sync: auto <UTC-timestamp>` in the format
`YYYY-MM-DDTHH:MM:SSZ`. A clean tree SHALL produce no commit.

#### Scenario: Dirty tree on sweep commits

- **WHEN** a `SYNC_SWEEP` event is processed and the working tree has uncommitted
  changes (e.g. a new attachment)
- **THEN** a single `sync: auto <timestamp>` commit captures them

#### Scenario: Clean tree on sweep is a no-op

- **WHEN** a `SYNC_SWEEP` event is processed and the working tree is clean
- **THEN** no commit is created

#### Scenario: An MCP write committed before its watcher echo is not double-committed

- **WHEN** an `MCP_WRITE` for a file is processed (and committed) and a later
  `SYNC_SWEEP` for the same unchanged file is then processed
- **THEN** the sweep finds nothing to commit and creates no duplicate commit

### Requirement: Commit and push are decoupled and debounced

The worker SHALL commit per event but SHALL NOT push on every commit. It SHALL
push after the queue has been quiet for a configurable debounce window, and SHALL
guarantee a push within a configurable maximum interval while the queue stays
busy. When no remote is configured, the worker SHALL commit only and never push.

#### Scenario: Push batches multiple commits after quiet

- **WHEN** several events are processed in quick succession and then the queue
  goes quiet for the debounce window
- **THEN** one push delivers all the accumulated commits

#### Scenario: Commit-only when no remote configured

- **WHEN** no remote is configured and events are processed
- **THEN** commits are created and no push is attempted

### Requirement: Local-wins sync without conflict markers

Before pushing, the worker SHALL `git fetch` and `git rebase -X theirs` the
remote tracking branch so local commits win on conflict. If the rebase fails the
worker SHALL `git rebase --abort` and log — it SHALL NEVER leave or commit files
containing conflict markers. If the fetch fails (e.g. offline), the worker SHALL
skip the rebase and still attempt the push.

#### Scenario: Diverged remote is rebased local-wins

- **WHEN** the remote has commits the local branch lacks and a push is due
- **THEN** the worker fetches and rebases `-X theirs`, then pushes, with no
  conflict markers committed

#### Scenario: Rebase failure aborts cleanly

- **WHEN** a rebase cannot complete
- **THEN** the worker aborts the rebase and logs, leaving the working tree free of
  conflict markers

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
