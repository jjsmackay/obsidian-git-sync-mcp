# container-ci Specification

## Purpose
TBD - created by syncing change container-build-workflow. Update Purpose after sync.
## Requirements
### Requirement: Workflow builds both images

A GitHub Actions workflow at `.github/workflows/build-containers.yml` SHALL build
both container images of the stack — the `mcp` image from the root `Dockerfile`
and the `obsidian-sync` sidecar from `obsidian-sync/Dockerfile` — on every push
to `main`, on every pull request targeting `main`, and on every `v*` tag. A
failure to build either image SHALL fail the workflow.

#### Scenario: Pull request builds both images

- **WHEN** a pull request targeting `main` is opened or updated
- **THEN** the workflow builds the `mcp` image and the `obsidian-sync` image
- **AND** the workflow fails if either build fails

#### Scenario: Broken Dockerfile fails CI

- **WHEN** a change makes either `Dockerfile` fail to build
- **THEN** the workflow run reports failure

#### Scenario: Upstream git pin resolves during build

- **WHEN** the `mcp` image build installs this package
- **THEN** the build can reach GitHub to resolve the `obsidian-web-mcp`
  git-branch dependency over https, with no extra credential

### Requirement: Pull requests build without pushing

On pull-request events the workflow SHALL build the images for validation only
and SHALL NOT push any image to a registry. Registry login SHALL be skipped on
pull-request events.

#### Scenario: Pull request does not publish

- **WHEN** the workflow runs for a pull request
- **THEN** no image is pushed to any registry
- **AND** the registry login step does not run

### Requirement: Push and tags publish to GHCR

On push to `main` and on `v*` tags the workflow SHALL push both built images to
the GitHub Container Registry under the repository owner's namespace
(`ghcr.io/<owner>/obsidian-mcp` for the `mcp` image and
`ghcr.io/<owner>/obsidian-sync` for the sidecar image). The workflow SHALL authenticate to
GHCR using the built-in `GITHUB_TOKEN` and SHALL declare `packages: write`
permission; it SHALL NOT require any manually configured secret.

#### Scenario: Push to main publishes latest

- **WHEN** a commit is pushed to `main`
- **THEN** both images are pushed to GHCR tagged `latest`

#### Scenario: Version tag publishes semver

- **WHEN** a `v*` tag is pushed
- **THEN** both images are pushed to GHCR tagged with the corresponding semver

#### Scenario: Authenticates with the built-in token

- **WHEN** the workflow logs in to GHCR
- **THEN** it uses `GITHUB_TOKEN` with `packages: write` and no manually
  configured secret

### Requirement: Images carry SHA and ref tags

Published images SHALL be tagged so that the source of each image is traceable:
the commit SHA on every published build, `latest` on `main`, and the semver on
`v*` tags. Tagging SHALL be derived from the event ref rather than hardcoded.

#### Scenario: Every published image is SHA-tagged

- **WHEN** an image is published from any qualifying event
- **THEN** it carries a tag identifying the commit SHA it was built from

### Requirement: Builds use layer caching

The workflow SHALL use the GitHub Actions build cache (`type=gha`) for both image
builds so that unchanged layers are reused across runs.

#### Scenario: Cache is read and written

- **WHEN** an image is built
- **THEN** the build reads from and writes to the GitHub Actions layer cache

### Requirement: Workflow file is valid

`.github/workflows/build-containers.yml` SHALL be valid YAML that GitHub Actions
can parse, with a defined trigger set (`push`, `pull_request`, tags) and the
required `permissions` block.

#### Scenario: Workflow parses

- **WHEN** the workflow file is linted or parsed as YAML
- **THEN** it parses with no error and declares its triggers and permissions

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

