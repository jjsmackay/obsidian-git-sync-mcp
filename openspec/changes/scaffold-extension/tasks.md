## 1. Project scaffold

- [ ] 1.1 Create `pyproject.toml` (uv + hatchling; no setuptools, no requirements.txt, no Node) for distribution `obsidian-git-sync-mcp`, import package `obsidian_git_sync`, `requires-python >=3.12`
- [ ] 1.2 Declare the upstream dependency `obsidian-web-mcp @ git+https://github.com/jjsmackay/obsidian-web-mcp@feat/write-listener` (TODO: repin to upstream once PR #62 merges) and a `dev` extra with pytest
- [ ] 1.3 Lay out the package: a module exposing `GitSyncExtension`, a `config` module for `VAULT_GITSYNC_*`, and a `main` entry point; declare the `[project.scripts]` console script
- [ ] 1.4 `uv sync` and confirm `uv run pytest` runs an (initially empty) suite green against the installed upstream

## 2. Configuration & gating

- [ ] 2.1 Implement env-var config loading from `VAULT_GITSYNC_*`, with a single enabling variable defaulting to disabled (mirror the upstream `config.py` idiom: raw strings parsed in the validator)
- [ ] 2.2 Implement `validate_gitsync()` that runs only when enabled and raises `ValueError` on missing/invalid config, with a clear message naming the offending value (never echoing secrets)
- [ ] 2.3 Document each `VAULT_GITSYNC_*` variable where it is read (names provisional; reconciled with `.env.example` in the container-deployment change)

## 3. Extension class & entry point

- [ ] 3.1 Implement `GitSyncExtension(Extension)` against the upstream #57 seam (`b1da366`): override hooks as no-ops this change; `before_indexes_start` runs `validate_gitsync()` as a fail-closed backstop when enabled
- [ ] 3.2 When disabled, the extension registers nothing and logs that it loaded but is off; `register_routes` stays a no-op (no `/health` — upstream-reserved)
- [ ] 3.3 Implement the console entry point: construct `GitSyncExtension()`, run `validate_gitsync()` with `ValueError → log → sys.exit(1)`, then `serve([ext])`

## 4. Tests

- [ ] 4.1 Test: disabled-by-default (no env vars) — `build_app([GitSyncExtension()])` registers no extension tools/routes and the app behaves as the stock server
- [ ] 4.2 Test: explicitly disabled registers nothing and does no work
- [ ] 4.3 Test: enabled with valid config passes `validate_gitsync()` and the extension loads
- [ ] 4.4 Test: enabled with invalid/missing config — `validate_gitsync()` raises `ValueError` naming the offending value; the entry point exits non-zero
- [ ] 4.5 Test: the extension adds no route that collides with an auth-exempt path (`build_app` does not raise)

## 5. Validation

- [ ] 5.1 Run `openspec validate scaffold-extension --strict` and resolve any findings
- [ ] 5.2 Confirm `uv run pytest` passes
