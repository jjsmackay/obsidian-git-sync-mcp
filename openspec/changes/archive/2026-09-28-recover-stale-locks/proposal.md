# Proposal

## Why

When a git command dies mid-operation and leaves its lock file behind, git sync
stops for good. Every later `git add` fails on the lock, and nothing in the
system removes it. The only way back is for a human to notice and delete a file
by hand. `surface-stage-failures` makes that failure visible, but it deliberately
leaves recovery out. This change adds recovery.

The incident behind both changes shows how the lock got orphaned, and that
shapes the design. A `git add` began and took `index.lock`. The whole host then
froze for about fifteen minutes; other services on the same host logged
single-query stalls of the same length. When the host resumed, the worker's
120-second git timeout fired at once, because its clock had frozen with
everything else. The timeout killed git and left the lock behind. A reboot came
28 minutes later, after the host had already recovered.

Two conclusions follow:

- **The timeout gives no guarantee.** A design that assumes "the timeout bounds
  the damage" is wrong whenever the whole host stops, because the timer stops
  too.
- **Recovery at startup is needed, but it is not enough on its own.** A startup
  check would have caught this incident only because a reboot happened to follow.
  Without the reboot, the container would have kept serving MCP with a dead git
  half indefinitely, and nothing would ever have prompted a restart. The runtime
  half is the degraded state from `surface-stage-failures`. The two changes
  complement each other; neither replaces the other.

## What Changes

- At startup, before the worker runs any git command, the extension looks for
  lock files git leaves in the repository (`index.lock`, `HEAD.lock`,
  `config.lock`, `packed-refs.lock`, and ref locks under `refs/`). It removes
  each lock that is stale.
- A lock counts as stale only when no git process is running and the lock is
  older than a fixed threshold. A lock that fails either test is left in place
  and logged.
- Every removal is logged at warning, naming the lock and its age. Clearing a
  lock silently would hide the evidence that something (such as a host freeze)
  went wrong, so nobody would ever learn of it.
- The sweep never refuses the boot. A stale lock is a recoverable git condition,
  and the MCP server served correctly throughout the incident; failing closed
  would take it down for no reason. Detect, clear, log, carry on.
- At runtime nothing is cleared. When a staging or commit failure marks the
  worker degraded and a lock file is present, the warning names the lock and its
  age, so the human reading it knows the cause straight away.

Explicitly **not** in scope:

- **Clearing locks at runtime.** Removing a lock that a live git process holds
  corrupts the repository, which is worse than the stall. Recovery happens only
  at the next restart.
- **The container HEALTHCHECK.** It asserts that the MCP port accepts
  connections. Failing it on git state would mark a correctly serving container
  unhealthy and mix up two independent subsystems. Git-sync liveness belongs to
  the heartbeat (`restore-kuma-monitoring`).
- **In-progress rebase or merge state** (`rebase-merge/`, `MERGE_HEAD`). The
  worker already aborts a failed rebase, and those states fail differently.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `git-worker`: gains stale-lock recovery at startup, and failure warnings that
  name a lock file when one is present.

## Impact

- New module `src/obsidian_git_sync/locks.py`: lock discovery, the staleness
  test and removal. It is pure filesystem work, with no git subprocess apart from
  resolving the git directory.
- `src/obsidian_git_sync/extension.py`: `after_indexes_start` runs the sweep
  before starting the worker, only when git sync is enabled, and never raises.
- `src/obsidian_git_sync/worker.py`: `_record_failure` adds the lock path and
  age to its warning when a lock is present.
- `tests/`: coverage for the sweep, the staleness gates and the runtime message.
- `README.md`: one troubleshooting paragraph on what the warning means and when
  a human still needs to act.
- No new configuration variable. The threshold is a constant tied to the git
  timeout.
- **Deployment note:** the first restart on this version clears any stale lock
  that is still present, and the first sweep after that commits everything that
  built up behind it, including deletions.
- Depends on `surface-stage-failures`, which introduces `_record_failure` and
  the degraded state that the runtime message builds on.
