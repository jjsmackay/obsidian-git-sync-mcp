## 1. Event model & queue

- [x] 1.1 Add `events.py` with a `SyncEvent` (kind: `MCP_WRITE` | `SYNC_SWEEP`; for `MCP_WRITE` an `operation` and `paths`; for `SYNC_SWEEP` a `trigger` source) — a small frozen dataclass or similar
- [x] 1.2 Add a thread-safe `EventQueue` wrapping `queue.Queue` (multi-producer, single-consumer) with `put`/`get` and a way to drain for tests

## 2. Config

- [x] 2.1 Add the sweep-interval `VAULT_GIT_*` env var (provisional name, e.g. `VAULT_GIT_SWEEP_INTERVAL`), default a sane value (e.g. 60s); parse/validate in `validate_gitsync()` (positive integer), failing closed

## 3. Producers wired into the extension

- [x] 3.1 In `before_indexes_start` (enabled only): register a write-listener that maps `(operation, paths)` → `MCP_WRITE` and enqueues it
- [x] 3.2 In `before_indexes_start` (enabled only): register a `.md` change-listener that maps a change → `SYNC_SWEEP(trigger=watcher)` and enqueues it
- [x] 3.3 In `after_indexes_start` (enabled only): start a daemon timer thread that enqueues `SYNC_SWEEP(trigger=timer)` every interval, controlled by a stop `Event`
- [x] 3.4 In `shutdown`: set the stop event so the timer thread exits and enqueues no more
- [x] 3.5 Keep all wiring behind the enable flag — disabled attaches nothing and starts no timer

## 4. Tests

- [x] 4.1 Test: a write-listener callback invocation enqueues an `MCP_WRITE` with the right operation + paths (drive via `obsidian_vault_mcp.write_events.fire_write` after the extension wired itself)
- [x] 4.2 Test: a change-listener callback invocation enqueues a `SYNC_SWEEP(trigger=watcher)`
- [x] 4.3 Test: the timer enqueues `SYNC_SWEEP(trigger=timer)` events on its interval (use a tiny interval; assert ≥1 enqueued, then stop)
- [x] 4.4 Test: `shutdown` stops the timer — no further events after it returns
- [x] 4.5 Test: concurrent enqueues from multiple threads lose nothing (queue thread-safety)
- [x] 4.6 Test: disabled extension registers no write/change listener and starts no timer
- [x] 4.7 Test: `validate_gitsync()` rejects a non-positive sweep interval when enabled

## 5. Validation

- [x] 5.1 Run `openspec validate change-trigger --strict` and resolve findings
- [x] 5.2 Confirm `uv run pytest` passes (existing scaffold tests + new ones)
