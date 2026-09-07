## Context

Upstream's extension seam (#57) is deliberately minimal: `serve(extensions=[...])`
takes a list, and the documented convention is that each extension ships its own
console entry point calling `serve([YourExtension()])`. There is no entry-point
group, no metadata scan, no registry — nothing in the upstream package composes
two extensions, and `serve()` is called once per process.

Our `main.py` follows that convention and therefore inherits its limit: it builds
one `GitSyncExtension`, runs `validate_gitsync()` fail-closed, and calls
`serve([ext])`. An operator who installs a second extension gets a second
`main()` that also wants to own the process. Neither can host the other, so the
only way to run both today is to fork an entry point.

The fix belongs in the entry point, which is the one place in this package whose
job is already "assemble the process". `main.py` also already owns the
fail-closed startup pattern (`ValueError → log → sys.exit(1)`) that new
validation should join rather than duplicate.

## Goals / Non-Goals

**Goals:**

- One `serve(...)` call can host `GitSyncExtension` plus extensions this package
  has never heard of, declared by the operator at deploy time.
- An unset variable is byte-for-byte today's behaviour, with no import machinery
  exercised.
- A bad declaration refuses the boot with a message naming the offending entry,
  in the same place and shape as `validate_gitsync()`.
- The mechanism carries no knowledge of any particular downstream extension —
  no names, no defaults pointing at one, nothing to keep this repo generic.

**Non-Goals:**

- Implicit discovery (entry-point groups, installed-package scans). Rejected on
  the trust model, not on effort — see Decisions.
- Passing constructor arguments to a declared extension. Import specs resolve a
  zero-argument class; anything an extension needs comes from its own env vars,
  which is how every extension in this ecosystem is already configured.
- Ordering control among declared extensions beyond declaration order, or
  inserting one ahead of `GitSyncExtension`.
- Sandboxing or privilege reduction for a declared extension. Upstream's trust
  model puts that out of reach in-process, and pretending otherwise would be
  worse than stating it.
- Contributing the mechanism upstream as part of this change. Worth doing later;
  it is not a precondition, and upstream has merged nothing since 2026-06-26.

## Decisions

**Declaration by env var, not implicit discovery.** An `entry_points` group
(`obsidian_vault_mcp.extensions`) would be the idiomatic Python answer and would
need no config at all — installing a package would load it. That is precisely the
objection. Upstream's own trust model states an extension "can read the bearer
token and OAuth secrets from the environment, read/write the vault, and mutate
any route… This is NOT a sandbox." Installing a package is not consent to run it
with those privileges, and a transitive dependency that happened to declare the
group would load silently. An explicit list makes the operator name every
extension they are trusting, and makes the loaded set auditable from the
deployment config rather than from `pip list`. It also degrades gracefully: if
upstream later adds discovery, our variable becomes redundant and is deleted,
rather than fighting it.

**`module.path:ClassName` import specs.** This is the same shape as
`[project.scripts]`, `[project.entry-points]`, and the `$module:$app` form every
ASGI and WSGI runner accepts, so it needs no explanation to an operator. The
alternative — a bare module path with a conventional attribute name
(`extension:Extension`) — buys nothing and constrains downstream naming.

**`VAULT_MCP_*`, not `VAULT_GIT_*`.** Every other variable this package reads is
`VAULT_GIT_*`, so this breaks a local pattern deliberately. The variable
configures the *server host* — which extensions the process runs — not git-sync,
and a git-sync-prefixed name for "load an unrelated extension" would be
actively misleading. `VAULT_MCP_*` is upstream's namespace and the namespace
downstream extensions already use for their own settings. The cost is that this
package defines a name inside a namespace it does not own; if upstream ever
defines `VAULT_MCP_EXTENSIONS` with different semantics, that collides. Accepted,
because the collision case is upstream implementing this same feature, at which
point we delete ours. Documented as "defined by this package until upstream
defines it".

**Resolve in the entry point, next to `validate_gitsync()`.** The failure mode we
want is a clean startup error, not a traceback from inside
`before_indexes_start`, and `main.py` already establishes exactly that pattern
for `validate_gitsync()`. Resolution therefore happens in `main()` before
`serve(...)`, raising `ValueError` for the entry point to log and exit on.
Parsing lives in `config.py` with the other lazily-validated accessors, so the
raw string is read at import and validated once at startup, matching the module's
stated shape.

**All-or-nothing resolution.** A list with one bad entry refuses the boot rather
than loading the good ones and warning. A half-loaded extension set is a silently
wrong deployment — the operator asked for a policy or a behaviour and got a
server running without it, which is the failure mode this repo's fail-closed
posture exists to prevent. It is also the same call `validate_gitsync()` makes.

**`GitSyncExtension` stays first.** Upstream runs each hook across extensions in
list order, so first position means git-sync's `before_indexes_start` registers
its write listener before any declared extension's hook runs. Keeping it first is
the conservative choice: this package's behaviour is unchanged by what an
operator declares, and a declared extension cannot pre-empt git-sync's
registration. Declared extensions then load in declaration order, which is the
only ordering an operator can reason about.

**Instantiate with no arguments, once each.** Resolution returns classes; the
entry point calls each once. A duplicate declaration therefore produces two
instances — harmless for a well-behaved extension, and not worth de-duplicating
silently, since a repeated entry is more likely a config mistake worth leaving
visible than an intent to load twice.

## Risks / Trade-offs

- **A declared extension runs fully-trusted in-process, with access to the
  bearer token, OAuth secrets, the vault and every route.** → Not mitigable
  in-process; upstream says so plainly. Mitigated by *disclosure and explicit
  opt-in*: the variable is unset by default, loading requires the operator to
  name the extension, and both the README and `.env.example` state the trust
  position at the point of configuration. The spec makes the no-implicit-discovery
  rule normative so it cannot be "improved" into a convenience later.
- **We define a name in upstream's `VAULT_MCP_*` namespace.** → Accepted, scoped,
  and documented as ours-until-upstream's. The collision scenario is upstream
  shipping the same feature, whose resolution is deleting our variable.
- **A declared extension can break the server in ways this package cannot
  predict** — a raising hook, a route colliding with an auth-exempt path (which
  upstream's `build_app()` already rejects fail-closed), an unbounded thread. →
  Out of scope by design: we validate that a declaration *resolves to an
  Extension subclass*, not that it behaves. The startup error surface stays
  honest about which entry was loaded, so a bad extension is attributable.
- **Import side effects run at resolution time**, before `serve(...)` and before
  the index starts. → Inherent to any import-based mechanism; resolution order is
  declaration order and happens once, so it is at least deterministic.
- **A downstream deployment could come to depend on this variable, making it a
  compatibility surface** for a repo whose thesis is git-sync. → Small and
  deliberate: five behaviours, all specified, no coupling to any particular
  extension.

## Migration Plan

No migration. The variable is unset by default and an existing deployment that
never sets it is unaffected — same extension list, same behaviour, no new import
path exercised. Rollback is unsetting the variable (or reverting the image tag),
with no state to unwind: nothing persists, and git-sync's own configuration and
behaviour are untouched.

Adoption is a deploy-time edit: set `VAULT_MCP_EXTENSIONS` in `.env`, ensure the
named package is installed in the image, restart. A downstream image can compose
this by building `FROM` the published image, installing its own extension package
and setting the variable, without any change to this repo.

## Open Questions

- Should the mechanism be offered upstream as a `serve()`-level feature, so
  extension composition stops being every downstream entry point's problem? Out
  of scope here; worth raising once this has run in anger, and it would make our
  variable redundant by design rather than by accident.
- Should `container-ci` gain an importability assertion for a declared extension,
  the way it already asserts the upstream write seam is importable? Deferred
  until there is a second extension in a published image to assert against.
