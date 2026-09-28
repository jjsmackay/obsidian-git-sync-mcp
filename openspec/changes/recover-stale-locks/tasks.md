# Tasks

> Depends on `surface-stage-failures` having landed: task 3.1 extends its
> `_record_failure`.

## 1. Lock discovery and staleness

- [ ] 1.1 Add `locks.py` with a discovery function returning each `*.lock`
  directly in the git directory and under `refs/` (recursively) with its age,
  resolving the git directory via `GitOps.git_dir()` (rev-parse only for a
  `.git` file, `<vault>/.git` fallback); verify with unit tests that index, HEAD and
  `refs/heads/<branch>` locks are found and that a `*.lock` under `objects/` is
  not
- [ ] 1.2 Add the live-git check over `/proc/*/comm`, excluding the current PID
  and returning "unknown" when `/proc` cannot be read; verify with unit tests
  against a fake proc root covering none, one git process, and unreadable
- [ ] 1.3 Add the staleness decision (no live git AND age at least
  `2 × DEFAULT_TIMEOUT`, with negative age treated as young); verify with unit
  tests for old+idle (clear), young, git running, and unknown process state

## 2. Startup sweep

- [ ] 2.1 Add the sweep: remove each stale lock with one warning naming its
  git-dir-relative path and human-readable age, log a warning for each lock left
  in place with the reason, and log a failed unlink without stopping; verify
  with unit tests asserting exactly one warning per removed lock and none on a
  clean repository
- [ ] 2.2 Call the sweep from `after_indexes_start` immediately before the worker
  starts, enabled only, wrapped so any exception is logged and startup continues;
  verify with unit tests that a raising sweep still starts the worker and that a
  disabled extension inspects no locks

## 3. Runtime message

- [ ] 3.1 In `_record_failure`, when logging at warning, append any present locks
  and their ages; verify with unit tests that a stage failure under an
  `index.lock` names it (and leaves it on disk) and that a failure with no lock
  is worded as before

## 4. Docs

- [ ] 4.1 Add a README troubleshooting paragraph: what the removed-lock and
  lock-present warnings mean, that recovery happens at the next restart, and to
  stop the container before running git against the vault from the host; verify
  by reading the rendered section

## 5. Verification

- [ ] 5.1 End to end against a temporary repository: create a back-dated
  `index.lock` and a back-dated `refs/heads/main.lock` with pending changes,
  start the extension, and verify both locks are removed with warnings, the
  worker starts, and the first sweep commits the backlog
- [ ] 5.2 Run the full suite with `uv run --extra dev python -m pytest` and
  verify it passes
