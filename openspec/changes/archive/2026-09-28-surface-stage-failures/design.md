# Design

## Context

See proposal.md — Why. The mechanics that matter:

- `GitOps.add()` and `GitOps.add_all()` both return a `GitResult` carrying the
  exit code. Both call sites discard it.
- `has_staged()` is `not _run("diff", "--cached", "--quiet").ok`. After a failed
  stage the index is empty, so this answers "nothing staged" — the same answer a
  genuinely clean tree gives. That equivalence is the bug.
- The worker is a single thread. Every cycle runs to completion before the next
  begins, and the only reader of any state added here runs on that same thread.
  No locking is needed or wanted.
- House pattern: git failures are logged and swallowed, never raised out of the
  worker thread. This change extends that rule to staging rather than departing
  from it.

## Goals / Non-Goals

**Goals:**

- A staging failure produces a log line naming the exit code and the path it
  occurred in.
- The worker carries a machine-readable answer to "did my last cycle actually
  work?", so a monitor can consume it without parsing logs.
- Zero behavioural change on a healthy deployment.

**Non-Goals:**

- Detecting or clearing a stale `index.lock`, or any other recovery. This change
  makes the failure visible; acting on it is separate.
- Retrying a failed stage. A retry against a persistent cause is a tight loop
  against a wedged repository; the existing cycle cadence already retries
  naturally on the next event.
- Surfacing the degraded state over HTTP or MCP. The consumer is the heartbeat in
  `restore-kuma-monitoring`; anything else is speculative.

## Decisions

### Inspect the staging result and skip the commit branch on failure

Both handlers capture the `GitResult`, log a warning on failure, and return
without consulting `has_staged()`. Falling through to `has_staged()` after a
failed stage is what makes the failure look like a clean tree, so the fix is to
stop asking a question whose answer is already known to be meaningless.

Alternative considered: let the flow continue and rely on the commit failing.
Rejected — the commit does not fail, because there is genuinely nothing staged.
The system's own consistency is what hides the fault.

### Degraded state is a flag on the worker, set at cycle end

A boolean the worker sets when a cycle's git commands failed and clears when a
cycle completes clean. Single-threaded, so no synchronisation.

Alternatives considered:

- *Log only, no state.* Logs reach a human reading them; nothing in the
  deployment reads them, which is how three and a half days passed. The
  monitoring change needs a value it can branch on.
- *Infer it from a dirty tree.* "Changes on disk but nothing committed" is a
  tempting independent signal, but `git status --porcelain` on every cycle walks
  the tree, and the inference needs a time threshold to avoid firing on the
  normal window between a write and its commit. It also fails in the same way
  during a locked-index incident. A flag set by the code that actually observed
  the failure is both cheaper and more truthful.

### Repeated identical failures are logged once, not once per cycle

Entering the degraded state logs at warning; subsequent failures of the same kind
while already degraded log at debug; recovery logs at info. The incident that
motivated this change ran for three and a half days with a cycle every ten
seconds — logging every occurrence would have produced tens of thousands of
identical lines, which is its own kind of silence.

The state transition is the event worth recording. A reader scanning the log
finds one warning marking the start and one info marking the end, rather than a
wall to page through.

## Risks / Trade-offs

- **A debug-level repeat could hide an evolving failure** — a different error
  arriving while already degraded would be quieter than it deserves. →
  Distinguish on the exit code: a failure whose code differs from the one that
  caused the current degraded streak logs at warning, as a new event.
- **The flag reports the last cycle, not the vault's true state.** A worker that
  has recovered still has a backlog of changes that were never committed until
  its next successful sweep. → Acceptable: the sweep is unconditional and stages
  the whole tree, so recovery commits the backlog on the first clean cycle. The
  flag's job is to answer "is the worker working", not "is everything committed".
- **No recovery is included**, so a stale lock still needs a human. → Deliberate,
  and stated in the proposal; the alternative risks clearing a lock a live
  process holds. Making the failure loud is what turns a three-day outage into a
  same-hour one.

## Migration Plan

No configuration, no data, no interface change. A healthy deployment behaves
identically; a broken one starts saying so. Rollback is reverting the commit.

Sequencing: this change lands before `restore-kuma-monitoring`, whose heartbeat
gate reads the degraded flag. Landing them the other way round would ship a
monitor that stays green through exactly the outage described in the proposal.
