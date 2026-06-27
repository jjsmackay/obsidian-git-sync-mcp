## Why

The change-detection capability puts classified events on a queue but nothing
drains them. This change adds the single worker thread that turns events into
git history — the heart of the project. It ports the proven logic of the
bobsidian `git-sync.sh` (commit-local-first, then local-wins rebase, then push,
never commit conflict markers) into one in-process consumer, replacing flock +
cron with structural single-thread serialisation.

## What Changes

- Add a `git-worker` capability: one daemon consumer thread that drains the
  `EventQueue` and performs **all** git work. No other thread touches git.
- Per event:
  - `MCP_WRITE` → stage the event's paths and commit `mcp: <operation> <paths>`
    (a single path, or `p1, p2, p3 (+N more)` when more than three) if anything
    is staged.
  - `SYNC_SWEEP` → `git add -A` and commit `sync: auto <UTC-timestamp>` if the
    tree is dirty.
- **Commit and push are decoupled.** Each event commits immediately (granular
  history); push is batched and debounced — the worker pushes after the queue
  has been quiet for a configurable window, with a configurable maximum interval
  so a continuously busy queue still pushes periodically.
- **Local-wins sync**, ported verbatim in spirit: `git fetch`, then
  `git rebase -X theirs origin/<branch>`; on rebase failure, `git rebase --abort`
  and log — **never** leave or commit conflict markers. If fetch fails (offline),
  skip the rebase and still attempt the push.
- **Never crash the server.** Every git failure in the worker is logged and
  swallowed (the upstream house rule); only `validate_gitsync()` fails closed, at
  startup.
- The worker starts in `after_indexes_start` and stops on `shutdown` (best-effort
  final flush). Frontmatter stamping is layered into this pipeline by the next
  change; the heartbeat ping is the monitoring change.

## Capabilities

### New Capabilities
- `git-worker`: the single consumer thread; the per-event commit logic with
  provenance-tagged messages; decoupled debounced push; the local-wins
  fetch/rebase/push sequence; fail-soft error handling.

### Modified Capabilities
<!-- None. The worker consumes the existing EventQueue and starts via the
     existing extension hooks; change-detection's requirements are unchanged. -->

## Impact

- New code: `git_ops.py` (thin `git` CLI wrapper) and `worker.py` (the consumer
  thread + commit/push policy); worker start/stop wired into `extension.py`.
- New `VAULT_GIT_*` config: remote (optional — empty = commit-only), branch,
  push debounce + max interval, optional commit author identity (names
  provisional).
- Drives the `git` CLI as a subprocess (no libgit2/pygit2), against the upstream
  `VAULT_PATH` working tree.
