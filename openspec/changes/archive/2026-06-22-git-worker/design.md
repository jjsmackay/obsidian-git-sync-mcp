## Context

`change-trigger` produces `MCP_WRITE` and `SYNC_SWEEP` events onto a thread-safe
`EventQueue` but nothing consumes them. The bobsidian origin did this work in
`scripts/git-sync.sh`, invoked two ways (an MCP post-write hook with
`MCP_OPERATION`/`MCP_PATHS` set, and a cron timer) and serialised with `flock`.
Its proven shape: stamp → commit MCP paths first (`mcp: <op> <paths>`) → sweep
the rest (`sync: auto <ts>`) → `fetch` → `rebase -X theirs origin/main` (abort on
failure, never commit conflict markers) → push → heartbeat on the timer path.

This change ports that into ONE in-process worker thread. The two invocation
modes collapse into two event kinds on one queue; `flock` is replaced by the fact
that a single thread does all git work. Stamping is layered in by the next
change; the heartbeat is the monitoring change.

## Goals / Non-Goals

**Goals:**

- One daemon consumer thread; the per-event commit logic; decoupled, debounced
  push; the local-wins fetch/rebase/push sequence; fail-soft errors.
- A thin `git` CLI wrapper (`subprocess`), runnable against any working tree, so
  the worker is unit-testable with a tmp `git init` + a bare remote.
- Preserve the bobsidian invariants exactly: commit-local-first, `-X theirs`,
  abort-on-conflict, offline-tolerant push.

**Non-Goals:**

- No frontmatter stamping yet (next change inserts the stamp step before staging
  an `MCP_WRITE`).
- No heartbeat ping (monitoring change).
- No `state.db` / principal attribution (v2). Provenance is only the coarse
  `mcp:`/`sync:` split.
- No libgit2/pygit2 — the `git` CLI only.

## Decisions

**One thread, blocking `get` with a debounce timeout.** The worker loop blocks on
`queue.get(timeout=debounce)`. An event wakes it → it commits immediately
(granular history). When `get` times out (the queue has been quiet for the
debounce window) and there are unpushed commits, it pushes. A `max_interval`
guard forces a push even if the queue never goes quiet, bounding push latency
under sustained load. This gives per-write commit granularity with batched pushes
from one simple loop — no separate timer, no second thread, no lock.

**Push decoupled from commit.** bobsidian pushed on every invocation; at MCP write
rates that is a push per keystroke-batch. Decoupling lets commits stay granular
(good history, matches the ~81% `mcp:` commit ratio the origin saw) while pushes
batch. Alternative considered: push on every commit. Rejected — needless remote
round-trips and rate-limit exposure.

**Commit-local-first, then rebase, then push — ported verbatim.** This is the
core correctness property: by committing local work before touching the remote,
a rebase conflict is resolved by `-X theirs` favouring our just-made commits, and
a failed rebase is `--abort`ed, so the working tree never ends up with conflict
markers that a later `git add -A` would commit and push. The stash-pop trap the
origin script's comment calls out is avoided the same way: we never stash.

**`git add -A` for sweeps, path-scoped add for MCP writes.** An `MCP_WRITE` knows
its paths, so it stages exactly those for a tight `mcp:` commit. A `SYNC_SWEEP`
cannot know what changed (it may be an attachment the .md watcher never saw), so
it stages everything. A delete/move still works under `git add -A` for the sweep,
and for `MCP_WRITE` the worker stages the named paths (git records the deletion of
a path that no longer exists when staged with `git add -A -- <path>` semantics).

**Remote optional → commit-only mode.** If no remote is configured the worker
commits and never pushes (a purely local audit trail / backup-to-disk). When a
remote IS configured, `validate_gitsync()` checks it exists at startup
(fail-closed). Branch defaults to the working tree's current branch.

**Fail-soft everywhere except startup validation.** Each git call is wrapped; a
non-zero exit is logged (host/exception type, not secrets) and swallowed so a
flaky network or a transient lock never takes down the MCP server. Unpushed
commits simply accumulate and the next push attempt retries them. This is the
upstream #45 house rule applied to the worker.

## Risks / Trade-offs

- [A wedged git operation could block the single worker thread] → Run git with a
  timeout; on timeout, log and move on. The worker thread is a daemon, so it never
  blocks process exit.
- [`shutdown` via atexit must be quick but should not lose commits] → On shutdown,
  signal stop, let the current git command finish, do one best-effort final
  commit+push of anything pending, then return. Bounded by the git timeout.
- [Concurrent external pushes can still race a push] → `-X theirs` + retry on the
  next cycle converges; worst case a push is rejected and retried, never a
  corrupted tree.
- [`git add -A` during a sweep could stage a partially-written file from an
  in-flight device sync] → The next sweep recommits the completed file; an
  interim commit of a partial file is self-healing and preferable to missing the
  change. Documented, not prevented.
