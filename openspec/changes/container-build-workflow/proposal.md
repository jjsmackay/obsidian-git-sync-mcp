## Why

The `container-deployment` and `obsidian-sync-sidecar` changes defined two
images — the `mcp` image (root `Dockerfile`) and the `obsidian-sync` sidecar
(`obsidian-sync/Dockerfile`) — but they are only ever built locally via
`docker compose build`. Nothing in CI proves the images still build, and there
are no published images, so every deployment has to clone and build from source.
A GitHub Actions workflow closes both gaps: it catches a broken `Dockerfile` (or
a broken upstream git-branch pin) on every push, and publishes ready-to-pull
images so operators can run the stack without a local build toolchain.

## What Changes

- Add `.github/workflows/build-containers.yml`: a GitHub Actions workflow that
  builds **both** images with Buildx — the root `mcp` image and the
  `obsidian-sync/` sidecar — on push to `main`, on pull requests, and on
  version tags.
- On pull requests: build only (validate the `Dockerfile`s), do not push.
- On push to `main` and on `v*` tags: build and push to GHCR
  (`ghcr.io/<owner>/obsidian-git-sync-mcp` and `…/obsidian-git-sync-mcp-sync`),
  authenticating with the workflow's built-in `GITHUB_TOKEN` (no new secrets).
- Tag images via `docker/metadata-action`: `latest` on `main`, the semver on
  tags, plus the commit SHA on every build.
- Use the GitHub Actions layer cache (`cache-from`/`cache-to: type=gha`) to keep
  rebuilds cheap, and build the `mcp` image for `linux/amd64` (matching the
  deployment target; multi-arch is left as a documented follow-up).
- Account for the upstream git-branch pin: the `mcp` build resolves
  `obsidian-web-mcp` from `git+https://…@feat/write-listener` (PR #62, pending),
  so the build step needs outbound network to GitHub — no extra credential,
  since it is a public repo.

## Capabilities

### New Capabilities
- `container-ci`: a GitHub Actions workflow that builds both container images on
  push/PR and publishes tagged images to GHCR on `main` and version tags, with
  build caching and no new secrets.

### Modified Capabilities
<!-- None. This adds CI/publishing around the existing images; it does not change
     the Dockerfiles or any runtime requirement in container-deployment or
     obsidian-sync-sidecar. -->

## Impact

- New file: `.github/workflows/build-containers.yml`. No change to the
  `Dockerfile`s, `docker-compose.yml`, or any source.
- Requires the repo to have a GitHub remote with Actions enabled and package
  write permission for `GITHUB_TOKEN` (the workflow sets `packages: write`).
  No remote is configured yet, so the workflow is inert until one is added.
- Published images inherit the upstream `feat/write-listener` git pin until
  PR #62 merges and `pyproject.toml` is repinned; the image tag is the audit
  trail for which pin a given image was built from.
- Operators gain a `docker pull` path as an alternative to building from source;
  the README exposure/run docs can later reference the published images.
