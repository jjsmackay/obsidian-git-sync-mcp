## Why

Upstream's extension seam (#57) documents one convention: subclass
`extensions.Extension` and ship your own console entry point calling
`serve([YourExtension()])`. It provides no discovery, no registry, and no way to
compose two extensions — so every extension owns a rival `main()`, and installing
a second one gives an operator two entry points that cannot host each other. Our
`main.py` hardcodes `serve([GitSyncExtension()])` and inherits exactly that limit.

An operator with a second extension ready to run alongside git-sync currently has
to fork an entry point to load both. That is a deployment-composition problem
solved once, generically, in the entry point we already own.

## What Changes

- `main.py` gains an operator-declared list of **additional** extensions, read
  from a new `VAULT_MCP_EXTENSIONS` environment variable as comma-separated
  `module.path:ClassName` import specs, and hands
  `serve([GitSyncExtension(), *extras])` to the upstream server.
- The variable is **unset by default**; unset or empty means today's behaviour
  exactly — a single-extension server, no import machinery exercised.
- Resolution is validated **fail closed** at startup, in the same place and with
  the same `ValueError → log → sys.exit(1)` handling as `validate_gitsync()`: an
  unimportable module, a missing attribute, a target that is not an
  `Extension` subclass, or a malformed spec refuses the boot with a message
  naming the offending entry. A half-loaded extension set never serves.
- `GitSyncExtension` stays first in the list, so its hooks run before any
  additional extension's at every lifecycle stage.
- The new variable uses the upstream `VAULT_MCP_*` namespace rather than this
  package's `VAULT_GIT_*`, because it configures the server host rather than
  git-sync. It is defined by this package until upstream defines it.
- Documentation states the trust position plainly: an additional extension is
  fully-trusted in-process code with the server's full privileges, per upstream's
  own trust model. Loading is explicit opt-in by design — never implicit
  discovery from what happens to be installed.
- `.env.example` and the README config table grow the new variable.

No new dependency. No change to git-sync behaviour, the worker, the commit split,
or the container topology. Not breaking: an existing deployment that never sets
the variable is byte-for-byte unaffected.

## Capabilities

### New Capabilities

- `extension-hosting`: The entry point composes the git-sync extension with
  additional operator-declared extensions — the `VAULT_MCP_EXTENSIONS` contract,
  import-spec resolution, fail-closed validation, load ordering, and the
  explicit-opt-in trust position.

### Modified Capabilities

- `git-sync-extension`: the "Extension loads into the MCP server" requirement
  currently fixes the load call as `serve(extensions=[GitSyncExtension()])`. It
  changes to admit additional extensions after `GitSyncExtension`, while keeping
  the in-process, no-separate-daemon guarantee and `GitSyncExtension`'s position
  as the first-loaded extension.
- `container-deployment`: the "Env-example documents the full surface"
  requirement is scoped to upstream `VAULT_*` plus ALL `VAULT_GIT_*` variables.
  It widens to cover the `VAULT_MCP_*` variables this package itself reads, so
  the new variable falls inside the documented surface instead of outside it by
  construction.
- `docs`: the "Configuration is documented accurately" requirement is likewise
  scoped to `VAULT_GIT_*` variables the code reads. It widens to include the
  `VAULT_MCP_*` variables this package reads, with the same exactness rule in
  both directions.

## Impact

- `src/obsidian_git_sync/main.py` — resolve and append the extra extensions.
- `src/obsidian_git_sync/config.py` — read the raw variable at import, parse and
  validate it lazily, alongside the existing `VAULT_GIT_*` accessors.
- `.env.example`, `README.md` — document the variable and the trust position.
- `tests/` — resolution success, each rejection mode, ordering, and the
  unset-is-a-no-op case.
- No upstream API is added or relied on beyond the existing `#57` seam and
  `server.serve`; the change is confined to how this package calls it.
