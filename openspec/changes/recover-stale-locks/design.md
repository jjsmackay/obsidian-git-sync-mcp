# Design

## Context

See proposal.md, Why. The mechanics that matter:

- Git takes a lock by creating `<file>.lock` with `O_CREAT|O_EXCL`, then renames
  it over the target on success or unlinks it on failure. A killed process does
  neither. No kernel lock is held (no `flock`, no `fcntl`), so there is nothing
  to probe: the only evidence of an owner is a running git process.
- The mcp container is the only thing that runs git against the vault. The
  Obsidian Sync sidecar mounts the same tree but runs `ob`, not git. At the
  point the worker starts, the worker itself has run no git command.
- `validate_gitsync()` runs read-only git commands (`remote get-url`, config
  reads), and those take no lock. Everything that writes goes through the
  worker thread, which starts in `after_indexes_start`.
- `GitOps` has a fixed `DEFAULT_TIMEOUT` of 120 seconds. No configuration
  overrides it.
- `surface-stage-failures` routes every staging and commit failure through one
  function, `_record_failure`, which is where the runtime message hooks in.

## Goals / Non-Goals

**Goals:**

- An orphaned lock is gone after the next restart, with no human involved, and
  the log says what was removed and how old it was.
- A lock that might have a live owner is never removed.
- A runtime failure caused by a lock says so in the log.

**Non-Goals:**

- Watching for locks between restarts, or prompting a restart. The degraded
  state reports the stall; acting on it is the heartbeat's and the operator's
  job.
- Protecting against git processes outside the container's PID namespace. The
  age threshold is the only defence there (see Risks).

## Decisions

### Run the sweep in the extension, just before the worker starts

`after_indexes_start` calls the sweep and then starts the worker, only when git
sync is enabled, inside a `try/except Exception` that logs and carries on.

Alternatives considered:

- *Beside `validate_gitsync()` in `main.py`.* That block turns a `ValueError`
  into `sys.exit(1)`. The sweep must never be able to stop the boot, and keeping
  it out of that block removes the temptation to raise. The extension is also
  the unit that owns git, and it is what the tests drive.
- *In `before_indexes_start`.* That also works, but the worker start is the real
  boundary. Running the sweep immediately before the worker is created keeps the
  "no git process of ours exists yet" argument true by construction.

### Discover locks by location, not by a hard-coded name list

Candidates are every `*.lock` directly inside the git directory (index, HEAD,
ORIG_HEAD, config, packed-refs, shallow and any future sibling), plus every
`*.lock` under `refs/`, recursively. `objects/`, `logs/` and `modules/` are not
searched. Nothing git writes there as a lock would block the worker's staging or
commit path, and a broad glob would meet pack and submodule internals we have no
business touching.

The git directory comes from `GitOps.git_dir()`, which keeps `GitOps` the only
path to the git binary. When `<vault>/.git` is a directory it is used directly,
with no subprocess. Otherwise `git rev-parse --absolute-git-dir` resolves a
`.git` file pointing elsewhere; that command takes no lock. If it fails, the
fallback is `<vault>/.git`. `locks.py` itself only does filesystem work.

Alternative considered: `index.lock` only. Rejected. It is the lock this incident
produced, but a freeze during a ref update orphans `refs/heads/<branch>.lock`,
which blocks every commit with an error that is just as silent.

### Staleness means no running git process AND age past a threshold

- **Live git check.** The sweep scans `/proc/*/comm` for a process named `git`,
  excluding its own PID. In the container that sees exactly the processes that
  could own a vault lock. If `/proc` is missing or unreadable, the answer is
  "unknown", and unknown means leave every lock alone.
- **Age threshold.** This is `2 × DEFAULT_TIMEOUT` (240 seconds), a module
  constant with no environment variable. No git command the worker runs holds a
  lock longer than the timeout before it is killed. Doubling it leaves margin for
  filesystem timestamp granularity and a slow kill. Age is `time.time() - mtime`.
  A negative age (mtime in the future, from clock skew) counts as young.

Both tests are required. The process check is the real safety gate. The
threshold keeps the logic honest if the "only this container runs git"
assumption ever stops holding, for example a human running git on the host
against the bind-mounted vault.

Alternative considered: a configurable threshold. Rejected for now; there is no
operator decision it would serve, and a new variable must be documented,
validated and supported. It can be added if a real deployment needs it.

### Log every removal at warning, with age in human units

Each removal gets one warning:
`git-sync startup: removed stale lock index.lock (age 3d 21h 12m)`. A lock left
in place gets one warning saying why ("git process running", "younger than
240s", "cannot inspect processes"). A failed unlink (permissions, race) is
logged at warning and does not stop the sweep. A clean repository logs nothing
above debug.

### Runtime: name the lock in the failure warning, never remove it

`_record_failure` asks the same discovery function for present locks when it is
about to log at warning, and appends `; lock present: index.lock (age 12m)`.
Debug-level repeats skip the lookup. The lookup is a handful of `stat` calls on
a path that only runs after a failure, so the healthy path pays nothing.

## Risks / Trade-offs

- **[Risk] A git process outside the container (on the host, on the
  bind-mounted vault) holds a lock during a restart.** → The process check
  cannot see it; only the 240-second threshold protects it. Host-side git
  against a live vault is already unsupported, because it races the worker
  regardless of this change. The README troubleshooting note says to stop the
  container before running git on the host.
- **[Risk] A restart within 240 seconds of the interruption leaves the lock.** →
  It is logged as young and left in place. The degraded state reports the
  stall, and the next restart clears it. Acceptable: waiting is the safe
  direction.
- **[Risk] Removing the lock does not repair whatever the interrupted command
  left half-done.** → For `index.lock`, git never modified the real index; the
  lock file is the uncommitted new version, so discarding it is exactly what
  git's own failure path does. For a ref lock, the ref still points at its old
  value. The first sweep restages the tree from disk, so the result is
  consistent either way.
- **[Trade-off] The first sweep after recovery commits the whole backlog in one
  `sync:` commit, deletions included.** → That is the correct content: it is
  what is on disk. It also matches how any sweep treats out-of-band changes.
  History keeps everything recoverable.

## Migration Plan

No configuration or interface change. On a healthy deployment the sweep finds
nothing and logs nothing above debug. On a deployment with an orphaned lock, the
first restart on this version removes it with a warning, and the first sweep
commits the backlog. Rollback is reverting the commit.

Sequencing: after `surface-stage-failures`, whose `_record_failure` the runtime
message extends. Independent of `restore-kuma-monitoring`.
