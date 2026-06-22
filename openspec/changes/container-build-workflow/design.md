## Context

`container-deployment` produced the root `Dockerfile` (the `mcp` image) and
`obsidian-sync-sidecar` produced `obsidian-sync/Dockerfile`. Both are built only
by `docker compose build` on an operator's machine. There is no CI proof the
images build, and nothing is published — so a broken `Dockerfile` or a broken
upstream pin only surfaces at deploy time, and every deployment needs a local
build toolchain plus network access to resolve the `feat/write-listener` git
dependency.

Constraint that shapes the whole design: the `mcp` image installs
`obsidian-web-mcp` from a direct git reference
(`git+https://github.com/jjsmackay/obsidian-web-mcp@feat/write-listener`, PR #62
pending). The CI build must have outbound network to GitHub during `uv pip
install`. That repo is public, so this needs no credential — but it does mean the
build is not hermetic and the published image's identity depends on a moving
branch tip until #62 merges and `pyproject.toml` is repinned.

No GitHub remote is configured for this repo yet, so the workflow is inert until
one exists. This change ships the workflow so it is ready when the remote lands.

## Goals / Non-Goals

**Goals:**

- One workflow that builds both images on push/PR and fails on any build break.
- Publish tagged, traceable images to GHCR on `main` and `v*` tags, using only
  the built-in `GITHUB_TOKEN` — no new secrets to manage.
- Cheap rebuilds via the GitHub Actions layer cache.
- PRs validate the build without publishing (no registry writes from forks/PRs).

**Non-Goals:**

- Multi-arch images. Build `linux/amd64` (the deployment target); leave
  `linux/arm64` as a documented follow-up — it roughly doubles build time and
  needs QEMU, and there is no arm64 target yet.
- Running the test suite here. `uv run pytest` is a separate concern from
  container builds; a test workflow can be added later without entangling it
  with image publishing.
- Image signing / SBOM / provenance attestation. Worth doing later; not required
  to close the "images aren't built or published" gap.
- Changing any `Dockerfile`, the Compose file, or runtime behaviour.

## Decisions

**Single workflow, two build jobs (or a matrix), not two workflows.** Both images
share triggers, registry, permissions, and login. A matrix over
`{mcp: {context: ., image: obsidian-git-sync-mcp}, sync: {context: obsidian-sync,
image: obsidian-git-sync-mcp-sync}}` keeps the logic in one place and runs the two
builds in parallel. Two separate workflow files would duplicate the login and
metadata wiring.

**GHCR over Docker Hub.** GHCR authenticates with the workflow's built-in
`GITHUB_TOKEN` (`packages: write`), so there is nothing to provision — no Docker
Hub account, no `DOCKERHUB_TOKEN` secret. Images live next to the repo. This is
the lowest-friction publishing target for a GitHub-hosted repo.

**Standard `docker/*` actions: `setup-buildx-action`, `login-action`,
`metadata-action`, `build-push-action`.** These are the maintained, conventional
building blocks. `metadata-action` derives tags/labels from the event ref
(`type=ref` / `type=semver` / `type=sha`) so tagging is not hardcoded and the SHA
tag gives every published image a traceable origin. `build-push-action` takes
`push: ${{ github.event_name != 'pull_request' }}` so PRs build-only.

**`type=gha` cache for both builds.** `cache-from`/`cache-to: type=gha,mode=max`
reuses unchanged layers across runs — the apt + uv install layers dominate build
time, so caching them is the main lever. Each matrix leg uses a distinct cache
scope so the two images don't evict each other.

**Login gated on non-PR events.** `pull_request` builds must not push (a fork PR
has no write token anyway), so the login step carries an
`if: github.event_name != 'pull_request'` guard and `build-push-action`'s `push`
flag mirrors it. This keeps PR validation safe and publishing limited to trusted
refs.

**`packages: write` + `contents: read`, scoped in the workflow.** The workflow
declares exactly the permissions it needs; nothing more. No repo-wide token
elevation.

## Risks / Trade-offs

- [The `mcp` build depends on a moving upstream branch tip
  (`feat/write-listener`), so a green build today can break tomorrow if upstream
  force-pushes or the branch is deleted after #62 merges] → The SHA tag records
  exactly which commit each image was built from; the `pyproject` repin TODO
  (when #62 merges) removes the moving reference. Documented in the proposal.
- [amd64-only images won't run on arm64 hosts] → Matches the current deployment
  target; multi-arch is a documented follow-up, not a silent omission.
- [GHCR packages default to private; pulls then need auth] → Acceptable — package
  visibility is a one-time repo setting an operator flips if public pulls are
  wanted; the workflow doesn't depend on it.
- [Workflow is inert with no remote configured] → Intentional; it ships ready and
  activates when the remote and Actions are enabled. Stated in Impact.

## Migration Plan

Additive: drop in `.github/workflows/build-containers.yml`. It activates on the
next push/PR once a GitHub remote with Actions is configured. Rollback is
deleting the file — no runtime or image change to revert.

## Open Questions

- Should published GHCR packages be public or private? Defer to a repo setting;
  the workflow works either way.
- Add a separate test workflow (`uv run pytest`) as a PR gate? Out of scope here;
  worth a follow-up change.
