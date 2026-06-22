## Context

The scaffold extension validates and boots but observes nothing. The upstream
server exposes three ways to learn the vault changed, and they differ in what
they can see:

1. `write_events.register_write_listener(cb)` → `cb(operation, paths)` — fires on
   the success path of every MCP mutation tool (verified call sites in
   `tools/write.py` and `tools/manage.py`). Authoritative provenance: this change
   came through MCP. Operations: created / updated / moved / deleted.
2. `FrontmatterIndex.add_change_listener(cb)` → `cb(abs_path, exists)` — fires
   (debounced, `FRONTMATTER_INDEX_DEBOUNCE = 5.0s`) on **.md files only**. Sees
   on-disk changes regardless of origin, but is blind to attachments and canvas.
3. A periodic timer we own — sees nothing itself, but prompts a full-tree
   reconcile, which is the only thing that catches non-.md changes.

This change turns those three into one classified event stream. It deliberately
stops at "events on a queue" — the worker that drains them is the next change.

## Goals / Non-Goals

**Goals:**

- A `SyncEvent` model with two kinds, `MCP_WRITE` (operation + paths) and
  `SYNC_SWEEP` (trigger source), and a thread-safe `EventQueue`.
- The three producers wired at the right lifecycle points, gated by the enable
  flag.
- A periodic sweep timer that stops cleanly on shutdown.
- Tests that drive each producer and assert the right event lands on the queue,
  and that nothing is wired when disabled.

**Non-Goals:**

- No consumer, no git, no commits, no stamping (the git-worker change).
- No path-level dedup of an MCP write's watcher echo — that falls out of worker
  ordering (below), not from logic here.
- No backpressure / bounded queue tuning yet (noted as a risk).

## Decisions

**Two event kinds, not provenance-per-path.** The clean split the HANDOFF calls
for is: the write-listener is the *only* source that knows a change came through
MCP, so it alone produces `MCP_WRITE`. The watcher and the timer cannot know
origin, so they produce a kind-agnostic `SYNC_SWEEP` that means "stage whatever
is dirty and commit it as `sync:`". This avoids trying to infer provenance from
a filesystem event, which is unknowable. Alternative considered: tag every event
with a provenance guess and dedup downstream. Rejected — more state, more ways to
be wrong, for no gain over ordering.

**Double-commit avoidance is structural, deferred to the worker.** An MCP write
fires the write-listener (→ `MCP_WRITE`) AND, ~5s later, the .md watcher
(→ `SYNC_SWEEP`). With a single worker thread processing in order, the
`MCP_WRITE` is committed (`mcp:`) before the later sweep runs; by then that file
is already committed, so the sweep finds nothing new for it and emits no
duplicate `sync:` commit. The dedup is therefore a property of single-threaded
commit-then-sweep ordering, designed here but realised in the worker. This is
why the architecture mandates exactly one worker thread.

**Listeners attached in `before_indexes_start`, timer started in
`after_indexes_start`.** This mirrors the upstream hook contract: listeners must
be attached before the index starts watching so no change slips through between
build and attach; the timer depends on a built index and belongs after start.
`shutdown` (atexit, LIFO before `frontmatter_index.stop()`) stops the timer.

**`queue.Queue` for the event queue.** It is already thread-safe for
multi-producer / single-consumer, which is exactly this topology. A custom lock
+ list would re-implement it. The worker change will block on `.get()`.

## Risks / Trade-offs

- [No consumer yet → unbounded queue growth in a live server] → The git-worker
  change lands immediately after on the same branch; until then this is an
  interim state. Noted in the proposal, not hidden. A bounded queue / drop policy
  is a worker-change concern.
- [The 5s watcher debounce means an MCP write's echo and a near-simultaneous
  external edit can interleave] → Worker ordering still serialises them; worst
  case is an extra `sync:` commit, never a lost or corrupted one.
- [Timer thread must not outlive the process or wedge shutdown] → Use a daemon
  thread with a stop `Event`; `shutdown` sets it and the loop exits.
