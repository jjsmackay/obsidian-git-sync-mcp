# Tasks

## 1. Surface staging failures

- [x] 1.1 Capture `add_all()`'s result in `_handle_sync_sweep`, log a warning
  naming the exit code on failure, and return without consulting
  `has_staged()`; verify with a unit test that a failing stage logs and creates
  no commit
- [x] 1.2 Do the same for `add()` in `_handle_mcp_write`, with a message that
  distinguishes the MCP-write path from the sweep path; verify with a unit test
  asserting the two paths are distinguishable in the log output
- [x] 1.3 Verify the healthy paths are untouched: run the existing worker tests
  and confirm commit, push and no-op-on-clean-tree behaviour is unchanged

## 2. Cycle-health state

- [x] 2.1 Add the degraded flag to the worker, set when a cycle's staging or
  commit command fails; verify with unit tests covering a failed stage and a
  failed commit
- [x] 2.2 Clear the flag on a cycle that completes with no git failure; verify
  with a unit test that a failing cycle followed by a succeeding one leaves the
  worker not degraded
- [x] 2.3 Ensure a cycle that attempts no git command does not clear the flag;
  verify with a unit test that an `MCP_WRITE` carrying no paths leaves a
  degraded worker degraded

## 3. Log volume

- [x] 3.1 Log the transition into the degraded state at warning and repeats of
  the same exit code at debug while still degraded; verify with a unit test that
  three consecutive identical failures produce exactly one warning
- [x] 3.2 Log a failure whose exit code differs from the current streak's at
  warning, as a new event; verify with a unit test using two different exit
  codes
- [x] 3.3 Log recovery at info; verify with a unit test that the transition out
  of degraded produces exactly one info line

## 4. Verification

- [x] 4.1 Reproduce the real failure shape end to end against a temporary
  repository: create an `index.lock`, run a sweep, and verify the warning is
  emitted, no commit is created, and the worker reports degraded — then remove
  the lock, run another sweep, and verify the backlog commits and the flag
  clears
- [x] 4.2 Run the full suite with `uv run --extra dev python -m pytest` and
  verify it passes

## 5. Hand off to the monitoring change

- [x] 5.1 Confirm the degraded flag is readable from where the heartbeat gate
  will sit in `restore-kuma-monitoring`, on the worker's own thread and with no
  synchronisation needed; verify by reading the call site rather than adding
  code for it here
