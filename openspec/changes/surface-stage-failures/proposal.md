# Proposal

## Why

The worker discards the result of its staging commands. `add` and `add_all`
both return a result object; neither caller inspects it. When staging fails, the
index stays empty, the "is anything staged?" check answers no, no commit is
attempted, and nothing is logged — the failure is indistinguishable from a quiet
vault with nothing to commit.

This is not theoretical. A deployment hit it: a git command timed out, leaving an
orphaned `index.lock` in the vault, which made every subsequent `git add -A` fail
with rc 128. Git sync then did nothing for three and a half days while changes
accumulated on disk, and produced not one log line. The MCP server kept serving,
the container kept reporting healthy, and the device-sync sidecar was fine
throughout — only the git half was dead, invisibly.

The silence is the defect. A backup that has stopped backing up must say so.

## What Changes

- Staging results are inspected and logged, so a failed `git add` produces a
  warning naming the exit code, in both the MCP-write and sweep paths — the same
  treatment a failed commit already gets.
- The worker records whether its most recent event cycle completed without a git
  failure, and exposes that state. Logs alert a human reading them; this is the
  in-process half of the same signal, for a monitor to consume. It is the
  precondition for a heartbeat that can distinguish "nothing to commit" from
  "cannot commit" — see the `restore-kuma-monitoring` change, which depends on
  this one.
- The spec requirement that enumerates which git failures must be logged is
  corrected: it lists commit, fetch, rebase and push, and omits staging, which is
  precisely the hole the incident fell through.

Explicitly **not** in scope: detecting or clearing a stale `index.lock`. That is
the trigger this deployment happened to hit; the defect is the silence, which
would hide any staging failure whatever its cause. Lock handling — and whether
automatic clearing is safe at all, given that clearing a lock a live git process
legitimately holds is worse than the stall — is a separate change.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `git-worker`: staging joins the set of git failures that must be logged and
  swallowed, and the worker gains an observable notion of whether its last cycle
  completed cleanly.

## Impact

- `src/obsidian_git_sync/worker.py` — `_handle_mcp_write` and
  `_handle_sync_sweep` inspect their staging results; cycle-health state is
  recorded and cleared.
- `tests/test_git_worker.py` — coverage for a failing stage in both paths, and
  for the state transitions.
- No configuration change, no new variable, no behavioural change to a healthy
  deployment: a run in which nothing fails produces exactly the commits, pushes
  and logs it produces today.
- Unblocks `restore-kuma-monitoring`, whose heartbeat condition is unsound
  without this: with staging failures invisible, a wedged worker presents as an
  idle one and the monitor stays green through an outage.
