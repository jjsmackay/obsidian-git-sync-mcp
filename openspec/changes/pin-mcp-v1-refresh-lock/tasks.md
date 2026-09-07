## 1. Constrain the MCP SDK

- [ ] 1.1 Add a `[tool.uv]` block to `pyproject.toml` with
  `constraint-dependencies = ["mcp<2"]`
- [ ] 1.2 Comment the constraint with why it exists (upstream declares
  `mcp[cli]>=1.9.0` but targets the 1.x `mcp.server.fastmcp` API) and its removal
  condition (upstream caps the SDK itself, or migrates to 2.x)

## 2. Realign the lockfile

- [ ] 2.1 Relock the upstream package and the SDK:
  `uv lock --upgrade-package obsidian-web-mcp --upgrade-package mcp`
- [ ] 2.2 Confirm the locked upstream revision matches the `48ebdf0b` pin in
  `pyproject.toml` (the stale lock records `feat/write-listener#e63ec8da`)
- [ ] 2.3 Confirm the locked SDK version is on the 1.x line

## 3. Verify

- [ ] 3.1 Run the suite against the relocked environment:
  `uv run --extra dev python -m pytest` — all 124 tests pass
- [ ] 3.2 Reproduce the build's resolution in a clean throwaway checkout with no
  lockfile (`uv pip install .`) and confirm the resolved SDK is 1.x, not 2.x
- [ ] 3.3 In that same environment, confirm `obsidian_vault_mcp.server`,
  `obsidian_git_sync.main`, and `obsidian_vault_mcp.write_events.register_write_listener`
  all import with no `ModuleNotFoundError`
- [ ] 3.4 Confirm no `VAULT_GIT_*` variable, `.env.example` entry, or runtime
  behaviour changed — this change touches dependency metadata only

## 4. Record the follow-ups

- [ ] 4.1 Note that the upstream SDK cap against `jimprosser/obsidian-web-mcp` is
  owned outside this change, and that the constraint added here is removed when
  that cap merges and the upstream pin is bumped past it
- [ ] 4.2 Note the deferred locked-build shift (un-exclude `uv.lock`, install via
  `uv sync --frozen`) as its own future change
