## Context

The `mcp` image installs this package unlocked: `.dockerignore` excludes
`uv.lock`, and the Dockerfile runs `uv pip install --system .`. Dependency
resolution therefore happens at build time from `pyproject.toml` alone, and is
bounded only by what this project and upstream declare.

Upstream `obsidian-web-mcp` declares `mcp[cli]>=1.9.0` — a floor with no ceiling
— while its `server.py` imports `mcp.server.fastmcp.FastMCP`. The MCP Python SDK
released 2.0.0 on 2026-07-28 (2.1.1 current), renaming `FastMCP` to `MCPServer`
and deleting the `mcp.server.fastmcp` module. Reproduced against the current
`main` by installing unlocked into a clean environment: the resolver selects SDK
2.1.1 and the server fails on import with
`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`.

Nothing has rebuilt since 2026-07-13, which is why a published image has not yet
carried the fault. The workflow builds on every push to `main`, so the next
commit publishes it.

The second, quieter defect: `uv.lock` records the upstream dependency at
`?rev=feat%2Fwrite-listener#e63ec8da` while `pyproject.toml` pins `48ebdf0b`.
The test suite resolves through the lockfile, so the 124 tests currently green
are exercising a different upstream revision from the one the image ships.

## Goals / Non-Goals

**Goals:**

- An unlocked build resolves an MCP SDK the upstream server can import.
- The locked upstream revision matches the declared pin, so tests exercise the
  shipped server.
- The stopgap nature of the constraint is legible in the metadata, with a stated
  removal condition.

**Non-Goals:**

- Fixing upstream's metadata. The missing ceiling is upstream's defect and the
  durable fix is a one-line cap in their `pyproject.toml`. That contribution is
  owned outside this change. This change only stops the bleeding locally, and the
  constraint it adds is removed once that cap merges and the upstream pin is
  bumped past it.
- Migrating the upstream server to SDK 2.x. That is upstream's call, and it
  touches their `FastMCP` construction, transport arguments, and per-request
  lifespan — none of it this project's code.
- Changing how the image installs (see Decisions).

## Decisions

**Constrain, do not depend.** The bound goes in `[tool.uv]
constraint-dependencies = ["mcp<2"]`, not `[project.dependencies]`.

This project imports no `mcp` symbol anywhere — its entire contact with the
upstream server is `obsidian_vault_mcp.{extensions, write_events, server.serve,
config}` plus `FrontmatterIndex.add_change_listener`. Adding `mcp[cli]>=1.9.0,<2`
to `[project.dependencies]` would work, but it declares a direct dependency this
package does not have, and a future reader would reasonably infer the code uses
the SDK directly. A constraint says precisely what is meant: bound a transitive
without claiming it.

The mechanism was verified rather than assumed, because the `uv pip` interface
does not honour every `[tool.uv]` setting. Installing unlocked from a clean
checkout with the constraint present resolves SDK **1.29.1**, and both
`obsidian_vault_mcp.server` and `obsidian_git_sync.main` import cleanly, as does
`register_write_listener`.

*Alternative rejected — cap in `[project.dependencies]`:* works identically at
resolve time, but misstates the dependency graph.

**Keep the unlocked build.** Switching the Dockerfile to a locked install
(`uv sync --frozen`, un-excluding `uv.lock`) would make image contents exactly
reproducible and would have prevented this class of drift outright. It is the
better long-run posture and worth its own change, but it is a larger shift: it
changes what the image installs from, how the layer cache behaves, and how the
upstream pin is bumped. Bundling it here would couple an urgent one-line unblock
to a build-system change. Deferred deliberately, not overlooked.

**Refresh the lock so it agrees with both the pin and the constraint.** Relock
the upstream revision *and* the SDK, so the locked SDK is also the newest
compatible 1.x. Leaving the SDK at its currently-locked 1.28.0 while the image
resolves 1.29.1 would satisfy the letter of the lockfile-agreement requirement
on the upstream pin while preserving a smaller version of the same test/ship gap.

*Alternative rejected — relock only the upstream pin:* a narrower diff, but keeps
tests and image on different SDK patch lines for no benefit.

## Risks / Trade-offs

**The constraint outlives its usefulness and silently blocks a legitimate SDK 2.x
upgrade** → The removal condition is stated in the comment beside it, and the
spec requires that comment. When upstream migrates, this line is the first thing
to delete; the pin bump that accompanies such a migration forces a look at it.

**Upstream never merges the cap, so the stopgap becomes permanent** → Acceptable.
It costs one line and is correct for as long as upstream targets 1.x. The upstream
PR is tracked as separate work, not a blocker for this change.

**`mcp<2` is broader than the true compatibility range** → If upstream turns out
to need a narrower floor (some 1.x release breaking their usage), the constraint
will not catch it. Mitigated by the import-check scenario: the requirement is that
the server actually imports, not merely that a version was selected.

**Relocking may move unrelated transitives** → The relock is scoped to the
upstream package and the SDK, and the 124-test suite runs against the result
before commit; a green suite against the realigned lock is the gate.

## Migration Plan

No runtime migration: no environment variable, volume, or behaviour changes, so
deployments need no operator action beyond pulling a rebuilt image.

1. Add the constraint, relock, run the suite.
2. Merge to `main`; the workflow rebuilds and publishes a working `latest`.
3. Deployments pull the new image at their convenience — the currently-running
   containers are unaffected, since they were built before SDK 2.0.0 and hold a
   working 1.x.

Rollback: revert the commit. The previously published image predates the break
and remains functional, so there is no forward-only step to undo.

## Open Questions

None blocking. Two follow-ups are recorded elsewhere: the upstream SDK cap (with
the OAuth change), and the locked-build Dockerfile shift.
