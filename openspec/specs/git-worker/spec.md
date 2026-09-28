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
