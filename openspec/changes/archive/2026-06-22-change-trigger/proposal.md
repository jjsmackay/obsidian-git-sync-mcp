## Why

The scaffold extension boots but detects nothing. Git sync needs to know *when*
the vault changes and *where the change came from*, so the worker (next change)
can split history into provenance-tagged commits: `mcp:` for writes that came
through the MCP server, `sync:` for out-of-band changes (device edits via
Obsidian Sync, attachments dropped on disk). This change wires the three
detection sources the upstream server exposes and turns them into a single
stream of classified events. It does no git work — it produces the events the
worker will consume.

## What Changes

- Add a `change-detection` capability: a `SyncEvent` model and a thread-safe
  event queue.
- Classify detection into two event kinds:
  - **`MCP_WRITE`** (operation + paths) — from `register_write_listener` (#62);
    a write came through the MCP server. Carries the paths it touched.
  - **`SYNC_SWEEP`** (trigger source) — from `FrontmatterIndex.add_change_listener`
    (the .md watcher) **and** a periodic timer. Signals "reconcile the working
    tree"; carries no specific paths.
- Wire the producers at the correct upstream lifecycle points, **only when the
  extension is enabled**:
  - `before_indexes_start`: attach the write-listener and the change-listener
    (attached before the index starts so no change is missed).
  - `after_indexes_start`: start the periodic sweep timer.
  - `shutdown`: stop the timer.
- The timer sweep is **load-bearing, not a backstop**: `add_change_listener` is
  .md-only, so attachments and canvas files are only ever caught by the timer.
- Enqueue only; **no consumer yet**. The git worker (next change) drains the
  queue. The `mcp:`/`sync:` commit decision and the commit-then-sweep ordering
  that avoids double-committing an MCP write's watcher echo are worker behaviour,
  documented here but implemented next.

## Capabilities

### New Capabilities
- `change-detection`: the event model, the thread-safe queue, and the three
  producers (write-listener, .md change-listener, periodic timer) wired into the
  extension lifecycle and gated by the enable flag.

### Modified Capabilities
<!-- None. The producers attach via the existing extension lifecycle hooks, but
     the git-sync-extension requirements (load, gating, validation, entry point)
     are unchanged; the new behaviour is additive and lives in change-detection. -->


## Impact

- New code: `events.py` (the `SyncEvent` model + `EventQueue`), producer wiring
  in `extension.py`, a sweep timer.
- New dependency on upstream symbols: `write_events.register_write_listener`
  (#62, fork branch `feat/write-listener`) and
  `FrontmatterIndex.add_change_listener`.
- New `VAULT_GITSYNC_*` config: the sweep interval (name provisional).
- Without the worker (next change) the queue grows unbounded in a running
  server; the two changes ship back-to-back, so this is a within-branch interim
  state, noted not hidden.
