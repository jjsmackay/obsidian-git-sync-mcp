## ADDED Requirements

### Requirement: Build resolves an importable MCP SDK

The `mcp` image build SHALL resolve a version of the MCP Python SDK that the
upstream `obsidian-web-mcp` server can import. Upstream declares the SDK with a
lower bound only, and its code targets the 1.x API (`mcp.server.fastmcp.FastMCP`,
removed in SDK 2.0.0), so an unconstrained resolution can install an SDK major
whose modules the server does not import. This project SHALL therefore constrain
the transitive SDK to the compatible major line, and SHALL express that as a
resolver constraint rather than a declared dependency, because this package
imports no SDK symbol of its own.

The constraint is a stopgap for an upstream metadata defect. It SHALL carry a
comment naming the removal condition: upstream bounding the SDK itself, or
upstream migrating to the newer major.

#### Scenario: Unlocked install rejects an incompatible SDK major

- **WHEN** the `mcp` image build runs `uv pip install --system .` with no lockfile
- **THEN** the resolved MCP SDK is on the major line the upstream server targets
- **AND** an SDK major that removed the server's import path is not installed

#### Scenario: Installed server imports cleanly

- **WHEN** the built image imports the upstream server module and this project's
  console entry point
- **THEN** both import with no `ModuleNotFoundError`
- **AND** the upstream write seam `register_write_listener` is importable

#### Scenario: Constraint records why it exists

- **WHEN** a reader inspects the dependency metadata
- **THEN** the constraint is accompanied by the reason and the condition under
  which it is removed

### Requirement: Lockfile agrees with the declared upstream pin

The committed `uv.lock` SHALL record the same upstream `obsidian-web-mcp`
revision that `pyproject.toml` declares. The container build installs unlocked
while local development and the test suite resolve through the lockfile, so a
disagreement means the tested server and the shipped server are different code —
a divergence that hides breakage from the tests meant to catch it.

#### Scenario: Locked revision matches the declared pin

- **WHEN** the locked upstream revision is compared with the pin in
  `pyproject.toml`
- **THEN** the two identify the same commit

#### Scenario: Test suite passes against the locked revision

- **WHEN** the test suite runs against the environment resolved from the lockfile
- **THEN** every test passes
