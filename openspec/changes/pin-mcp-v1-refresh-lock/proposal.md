## Why

The `mcp` image no longer builds a working server. Upstream `obsidian-web-mcp`
declares `mcp[cli]>=1.9.0` with no upper bound, but its code is MCP-SDK-1.x-only
(`from mcp.server.fastmcp import FastMCP`). The SDK released 2.0.0 on 2026-07-28
(latest 2.1.1), which renamed `FastMCP` to `MCPServer` and deleted the
`mcp.server.fastmcp` module. Because `.dockerignore` excludes `uv.lock` and the
Dockerfile runs an unlocked `uv pip install --system .`, every build now resolves
SDK 2.x and produces an image that dies on import:

```
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

The last successful build was 2026-07-13, before 2.0.0 landed, so no rebuild has
happened yet — but the next push to `main` publishes a broken `latest`.

Separately, `uv.lock` is stale. It still records the upstream dependency at
`?rev=feat%2Fwrite-listener#e63ec8da` while `pyproject.toml` pins commit
`48ebdf0b`, so local tests and the container run different upstream code.

## What Changes

- Constrain the transitive MCP SDK to the 1.x line via
  `[tool.uv] constraint-dependencies` in `pyproject.toml`, so an unlocked
  `uv pip install .` resolves an SDK the upstream server can actually import.
  A constraint (not a `[project.dependencies]` entry) is the accurate mechanism:
  this package imports no `mcp` symbol and must not claim a dependency it does
  not use.
- Refresh `uv.lock` so the locked upstream revision matches the `pyproject.toml`
  pin, ending the divergence between the tested and shipped server.
- Document the constraint as a stopgap with an explicit removal condition: the
  bound belongs in upstream's own metadata, and is removed here once upstream
  either caps the SDK or migrates to 2.x.

Not in scope: the upstream fix itself (a one-line cap in
`jimprosser/obsidian-web-mcp`, contributed separately alongside the outstanding
OAuth protected-resource change), and any migration of the upstream server to
SDK 2.x.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `container-ci`: the requirement set covering what the `mcp` image build must
  resolve gains a bound on the transitive MCP SDK major version. Today the specs
  require only that the upstream git pin resolves over https; that is satisfied
  by a build whose resolved SDK cannot be imported, so the spec admits a broken
  image. The new requirement closes that gap and adds the lockfile-agreement
  obligation.

## Impact

- `pyproject.toml` — adds a `[tool.uv]` constraint block.
- `uv.lock` — regenerated; upstream revision realigned to `48ebdf0b`.
- `.github/workflows/build-containers.yml` — unchanged, but its `mcp` build stops
  producing a broken image.
- No source, runtime, or configuration change: no `VAULT_GIT_*` variable is added
  or altered, and the extension's behaviour is untouched.
- The upstream write seam this project depends on (`register_write_listener` /
  `fire_write`, upstream PR #62) is unaffected — it is pure Python with no SDK
  import, so it works identically under either SDK major.
