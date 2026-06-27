## 1. Git CLI wrapper

- [x] 1.1 Add `git_ops.py`: a thin wrapper running `git -C <vault>` via `subprocess` with a timeout, returning rc/stdout/stderr; never echo secrets in logs. Helpers for: `add(paths)` / `add_all()`, `commit(message)` (no-op-safe when nothing staged), `is_dirty()` / `has_staged()`, `fetch(remote)`, `rebase_theirs(remote, branch)` + `rebase_abort()`, `push(remote, branch)`, `current_branch()`, `remote_exists(remote)`
- [x] 1.2 Optional commit author identity: when configured, pass via `-c user.name=… -c user.email=…` (or `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env) on commit

## 2. Config

- [x] 2.1 Add `VAULT_GIT_*` (provisional names): `REMOTE` (default `origin`, empty = commit-only), `BRANCH` (default = current branch), `PUSH_DEBOUNCE` (seconds, default e.g. 10), `PUSH_MAX_INTERVAL` (seconds, default e.g. 300), optional `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`
- [x] 2.2 Extend `validate_gitsync()` (enabled only): debounce/max-interval positive numbers; when a remote is set it must exist (`git remote get-url`); fail closed with clear messages

## 3. Worker

- [x] 3.1 Add `worker.py`: a `GitWorker` with a `run()` loop — block on `queue.get(timeout=debounce)`; on an event, dispatch by kind; on timeout, push if there are unpushed commits
- [x] 3.2 `MCP_WRITE`: stage the event paths, commit `mcp: <op> <paths>` (single, or first-three + `(+N more)`) when staged; track that there are unpushed commits
- [x] 3.3 `SYNC_SWEEP`: `git add -A`, commit `sync: auto <YYYY-MM-DDTHH:MM:SSZ>` when dirty; track unpushed
- [x] 3.4 Push policy: debounce-quiet OR max-interval-exceeded → `fetch` → `rebase -X theirs` (abort+log on failure) → `push`; skip rebase if fetch fails; commit-only when no remote
- [x] 3.5 Fail-soft: wrap every git call; log + swallow failures; the worker keeps running and retries unpushed commits next cycle
- [x] 3.6 Wire into `extension.py`: start the worker thread in `after_indexes_start` (enabled only); on `shutdown` signal stop, do a best-effort final commit+push, return

## 4. Tests (tmp `git init` working tree + a bare remote; never a real remote)

- [x] 4.1 `MCP_WRITE` single path → one `mcp: <op> <path>` commit; many paths → `(+N more)` message
- [x] 4.2 `MCP_WRITE` with nothing staged → no commit
- [x] 4.3 `SYNC_SWEEP` dirty → one `sync: auto <ts>` commit (timestamp format asserted); clean → no commit
- [x] 4.4 MCP write committed, then a later sweep for the same unchanged file → no duplicate commit
- [x] 4.5 Push batching: several events then quiet → exactly one push delivers all commits (assert against the bare remote's log)
- [x] 4.6 Commit-only mode (no remote) → commits exist, no push attempted
- [x] 4.7 Diverged remote → fetch + `rebase -X theirs` + push leaves no conflict markers; a forced rebase failure → `--abort`, tree clean, worker still running
- [x] 4.8 A failing push is logged and swallowed; the worker keeps running and a later push succeeds
- [x] 4.9 Disabled extension → no worker thread, no git invoked
- [x] 4.10 `validate_gitsync()` rejects a missing remote / non-positive debounce when enabled

## 5. Validation

- [x] 5.1 Run `openspec validate git-worker --strict` and resolve findings
- [x] 5.2 Confirm `uv run pytest` passes (all prior tests + new ones)
