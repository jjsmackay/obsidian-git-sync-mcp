## 1. Config: read and resolve the declaration

- [ ] 1.1 Add `VAULT_MCP_EXTENSIONS = os.environ.get("VAULT_MCP_EXTENSIONS", "")` to `config.py` alongside the existing raw-at-import variables, with a comment noting it is the server-host namespace (not `VAULT_GIT_*`) and is defined by this package until upstream defines it
- [ ] 1.2 Add a `extra_extensions()` accessor that parses the raw value into a list of `Extension` subclasses: split on commas, strip whitespace, skip empty entries, and return `[]` for unset/empty/whitespace-only without importing anything
- [ ] 1.3 Resolve each entry as `module.path:ClassName` via `importlib.import_module` + `getattr`, raising `ValueError` naming the offending entry for: a malformed spec (no `:`, empty module, empty attribute), an unimportable module (chain the import error text), a missing attribute, or a target that is not an `extensions.Extension` subclass (report what it resolved to)
- [ ] 1.4 Extend `validate_gitsync()`, or add the equivalent call next to it, so a bad declaration is caught by the same startup validation path rather than only at resolution time

## 2. Entry point: compose the extension list

- [ ] 2.1 In `main.py`, resolve the declared extensions inside the existing `try` block that handles `validate_gitsync()`, so a `ValueError` logs and exits non-zero with a message naming the offending entry
- [ ] 2.2 Instantiate each resolved class once, with no arguments, and call `serve([GitSyncExtension(), *extras])` so `GitSyncExtension` is first and declared extensions follow in declaration order
- [ ] 2.3 Log at startup which additional extensions were loaded (import spec per entry), so the loaded set is attributable from the container logs; log nothing extra when none are declared

## 3. Tests

- [ ] 3.1 Unset, empty, and whitespace-only values each yield no additional extensions and import nothing (assert via a spec that would fail to import if touched)
- [ ] 3.2 One declared extension loads and reaches `serve(...)` after `GitSyncExtension`; assert list order explicitly
- [ ] 3.3 Several declared extensions load once each, in declaration order; whitespace-padded entries and a trailing/repeated comma are tolerated
- [ ] 3.4 Each rejection mode raises `ValueError` naming the entry: malformed spec, unimportable module, missing attribute, non-`Extension` target
- [ ] 3.5 A list mixing resolvable and unresolvable entries loads nothing and refuses to start (all-or-nothing)
- [ ] 3.6 `main()` exits non-zero and logs the offending entry on a bad declaration, matching the existing `validate_gitsync()` failure behaviour
- [ ] 3.7 An `Extension` subclass that is installed but undeclared is never imported or loaded
- [ ] 3.8 Full suite green: `uv run --extra dev python -m pytest`

## 4. Documentation

- [ ] 4.1 Add `VAULT_MCP_EXTENSIONS` to `.env.example`, unset/commented by default, in a section separate from the `VAULT_GIT_*` block, with the import-spec format and an example
- [ ] 4.2 State the trust position at the point of configuration in `.env.example` and the README: a declared extension is fully-trusted in-process code with the server's full privileges (bearer token, OAuth secrets, vault, routes), and extensions load only by explicit declaration, never by implicit discovery
- [ ] 4.3 Add the variable to the README config table with its default, keeping the documented set and the code-read set matching exactly in both directions
- [ ] 4.4 Document the downstream-composition pattern in the README: build `FROM` the published image, install another extension package, set the variable — no change to this repo required
