# Design

## Context

See proposal.md — Why. The relevant current state:

- `surface-stage-failures` lands first and adds the worker's degraded flag. This
  design reads it; it does not define it.
- `heartbeat.ping()` already implements the safe ping discipline (no redirects,
  bounded read, short timeout, host-only logging) and is already fail-soft. The
  git-sync work is a change of *trigger*, not of transport.
- The worker's push cycle runs from `_maybe_push()`, which returns early when
  nothing is unpushed or no remote is configured. It is entered every time the
  event queue stays quiet for the debounce window — 10s by default — so it is a
  far higher-frequency clock than a monitor wants.
- `obsidian-sync/healthcheck.sh` already computes the freshness verdict and is
  already wired as the image `HEALTHCHECK` on a 30s interval. It is deliberately
  network-free.
- The sidecar image is `node:22-bookworm-slim`, which ships **neither `curl` nor
  `wget`** (verified in the running container; `node`, `bash` and `stat` are
  present). The predecessor deployment's `curl -s` heartbeat cannot be ported
  verbatim.

## Goals / Non-Goals

**Goals:**

- One beat per healthy interval from each of the two images, consumable by a
  push-style monitor with a fixed expected interval.
- No new process, timer, or package in either image.
- The sidecar's health verdict stays exactly as decided today; reporting is
  strictly additive and cannot make a healthy sidecar look unhealthy.

**Non-Goals:**

- Recovery. No watchdog, no self-restart, no orchestrator integration.
- A pull-style health endpoint on the sidecar. Push covers container and host
  death with the same mechanism and needs no listener; a `/health` route would
  need a server process and an exposed port to answer a question the beat
  already answers.
- Plumbing the sidecar's other settings (freshness window, poll interval)
  through Compose. They stay overridable at the service level; widening that
  surface is unrelated to this change.

## Decisions

### The git beat fires on cycle outcome, not on the push call

Move the trigger from the `push.ok` branch to the end of the push cycle, gated on
"the worker is not degraded AND nothing is owed to the remote". Concretely: a
cycle is eligible when a remote is configured, the degraded flag from
`surface-stage-failures` is clear, and the unpushed flag is clear once the cycle
finishes — which covers both "a push just succeeded" and "there was nothing to
push".

The degraded term is not decoration. "Nothing owed to the remote" is satisfied
just as well by a worker whose staging fails before anything reaches the index:
nothing is staged, nothing is committed, nothing is unpushed, and the worker
looks idle. A two-term condition would have beaten steadily through the
three-and-a-half-day outage described in `surface-stage-failures`. This is also
why that change must land first — the flag has to exist before this gate can read
it.

Alternatives considered:

- *Keep push-only and widen the monitor's interval to hours.* Zero code, but the
  monitor then tolerates hours of a wedged worker, and the interval is a guess
  about editing habits rather than a property of the system.
- *Beat every cycle regardless of outcome* — what the predecessor's timer script
  did. Fixed cadence, but a push that fails forever keeps the monitor green.
  That is the flaw this design exists to avoid.

The chosen condition is the only one where all three failure modes that matter —
worker dead, cannot stage or commit, commits stuck unpushed — produce silence.

### The cadence floor lives in the worker, not in a timer

A monotonic timestamp of the last beat, compared against the interval at the
eligibility check. No thread, no scheduler. This keeps the beat a property of the
worker loop: if the loop stops turning, beats stop, which is precisely the signal
wanted. A separate timer thread would keep beating after the worker died.

The floor deliberately does not delay the first eligible beat — a monitor should
go green as soon as the worker is demonstrably healthy, not one interval later.

`VAULT_GIT_HEARTBEAT_INTERVAL`, default 60s, mirrors the upstream server's
`VAULT_MCP_HEARTBEAT_INTERVAL` in both name and default so an operator
configuring both is not learning two conventions.

### The sidecar beat wraps the healthcheck rather than living inside it

A new reporting script becomes the image's `HEALTHCHECK` command. It runs the
existing check, captures its exit code and output, sends the beat only on
success, and exits with the captured code.

Alternatives considered:

- *Ping from inside `healthcheck.sh`.* Fewer files, but then `docker exec
  <container> healthcheck` — the documented manual diagnostic — emits a beat and
  tells the monitor a one-off container is healthy. The check stops being safe to
  run by hand.
- *A background beat loop in the entry point.* Its own clock, independent of
  Docker, but it adds a process that must be reasoned about against the entry
  point's `exec` model, which the sidecar spec is deliberately strict about.

Docker's `--interval=30s` is the only recurring clock the image has without
adding a process, and 30s against the intended monitor interval leaves several
missed beats of tolerance.

### The ping is `node -e`, bounded well inside the healthcheck timeout

`node` is the only HTTP client in the image. The one-liner mirrors the idiom
already used for the mcp image's healthcheck (`python -c`), so both images stay
dependency-free in the same way.

The ping's own timeout must expire before Docker's healthcheck timeout, or a
hanging monitor would get the check *killed* and recorded as a failure —
inverting the requirement that reporting cannot change the verdict. Two guards:
a short ping timeout (single-digit seconds), and raising the image's
`HEALTHCHECK --timeout` to leave clear margin above it. The freshness check
itself is a `stat`, so a longer timeout costs nothing.

Redirect handling, the bounded read, and host-only error logging port directly
from `heartbeat.py`'s docstring rationale; the URL is a capability URL and must
never reach the output that Docker records in the health log.

## Risks / Trade-offs

- **A stuck rebase or a failing stage suppresses the git beat indefinitely, and
  the monitor cannot tell either from a dead worker.** → Intended: all need a
  human, and the worker's own logs say which it is. The upstream
  liveness heartbeat distinguishes them — it keeps beating if the process is
  alive — which is why the docs requirement makes operators configure all three
  rather than picking one.
- **The monitor's expected interval must exceed the cadence floor**, or a healthy
  deployment flaps. → Documented alongside the variable; the default floor (60s)
  sits well inside the intervals these monitors are normally given.
- **An un-bootstrapped sidecar never beats**, so its monitor sits down from the
  moment it is created until someone bootstraps. → Correct, and consistent with
  the existing healthcheck behaviour; called out in the sidecar README so it is
  not read as a fault.
- **Shell and Node in the sidecar are not covered by pytest.** The repo has no
  shell test harness and this change does not add one. → Verification for the
  sidecar half is a documented manual procedure against a local listener, plus
  the build-time assertion that no package was added. The git-sync half, where
  the subtle logic is, is fully unit-tested.
- **Health-log noise.** A failing beat prints a line that Docker stores in the
  health log every 30s. → Keep the failure line short and host-only; it is the
  same budget the existing verdict line uses.

## Migration Plan

Both beats are disabled when their variable is unset, and the git-sync trigger
change is only observable in a deployment that has a heartbeat URL configured —
today, none does. So the rollout is:

1. Ship the code; behaviour is unchanged everywhere until a URL is set.
2. Create the monitors, then set the variables in the deployment's environment
   file and restart. Each monitor goes green on the first healthy beat.
3. Rollback is unsetting the variables — no image change needed. Reverting the
   image restores push-only git beats, which is only a semantic regression for a
   deployment that had already adopted the new interval.

Order matters in two places: `surface-stage-failures` lands before this change,
and each monitor is created before its URL is set, or the first beats are
discarded.
