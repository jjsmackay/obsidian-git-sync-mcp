# change-detection Specification

## Purpose
TBD - created by archiving change change-trigger. Update Purpose after archive.
## Requirements
### Requirement: Classified change events

The extension SHALL represent a detected vault change as a `SyncEvent` with one
of two kinds:

- `MCP_WRITE` — carries the mutation `operation` (one of "created", "updated",
  "moved", "deleted") and the affected vault-relative `paths`.
- `SYNC_SWEEP` — carries the trigger source (the .md watcher or the periodic
  timer) and no specific paths.

`MCP_WRITE` events SHALL be produced only from the MCP write stream;
`SYNC_SWEEP` events SHALL be produced from the .md change watcher and the timer.

#### Scenario: A write-listener notification becomes an MCP_WRITE event

- **WHEN** the upstream write stream reports a mutation `(operation, paths)`
- **THEN** the extension enqueues a `SyncEvent` of kind `MCP_WRITE` carrying that
  operation and those paths

#### Scenario: A watcher notification becomes a SYNC_SWEEP event

- **WHEN** the .md change watcher reports a changed file
- **THEN** the extension enqueues a `SyncEvent` of kind `SYNC_SWEEP` tagged with
  the watcher as its trigger

### Requirement: Thread-safe event queue

The extension SHALL expose a thread-safe event queue onto which producers
enqueue `SyncEvent`s and from which a single consumer (added in a later change)
dequeues them. Enqueue SHALL be safe to call from multiple producer threads
(the MCP request thread, the watcher thread, the timer thread).

#### Scenario: Producers on different threads enqueue safely

- **WHEN** events are enqueued concurrently from more than one thread
- **THEN** every enqueued event is retrievable from the queue with none lost or
  corrupted

### Requirement: Producers wired only when enabled

When the extension is enabled, it SHALL attach the write-listener and the .md
change-listener in `before_indexes_start` (before the index starts watching, so
no change is missed) and start the periodic sweep timer in
`after_indexes_start`. When the extension is disabled, it SHALL attach no
listeners and start no timer.

#### Scenario: Enabled wires all three producers

- **WHEN** the enabled extension runs through `before_indexes_start` then
  `after_indexes_start`
- **THEN** a write-listener and a change-listener are registered upstream
- **AND** the periodic sweep timer is running

#### Scenario: Disabled wires nothing

- **WHEN** the disabled extension runs through its lifecycle hooks
- **THEN** no write-listener or change-listener is registered and no timer runs

### Requirement: Periodic sweep timer

When enabled, the extension SHALL run a periodic timer that enqueues a
`SYNC_SWEEP` event every configured interval, so that out-of-band changes the
.md watcher cannot see (attachments, canvas files) are still detected. The timer
SHALL stop on `shutdown`.

#### Scenario: Timer enqueues periodic sweeps

- **WHEN** the sweep interval elapses while the extension is enabled
- **THEN** a `SYNC_SWEEP` event tagged with the timer as its trigger is enqueued

#### Scenario: Shutdown stops the timer

- **WHEN** the extension's `shutdown` hook runs
- **THEN** the sweep timer stops and enqueues no further events

