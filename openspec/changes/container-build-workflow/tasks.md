## 1. Workflow skeleton

- [x] 1.1 Create `.github/workflows/build-containers.yml` with `name`, and triggers: `push` on `main` and `v*` tags, `pull_request` on `main`
- [x] 1.2 Declare `permissions: { contents: read, packages: write }`
- [x] 1.3 Define a build job with a matrix over the two images: `{name: mcp, context: ., dockerfile: Dockerfile, image: obsidian-mcp}` and `{name: sync, context: obsidian-sync, dockerfile: obsidian-sync/Dockerfile, image: obsidian-sync}`

## 2. Build steps

- [x] 2.1 `actions/checkout`, then `docker/setup-buildx-action`
- [x] 2.2 `docker/login-action` to `ghcr.io` with `username: ${{ github.actor }}` / `password: ${{ secrets.GITHUB_TOKEN }}`, gated `if: github.event_name != 'pull_request'`
- [x] 2.3 `docker/metadata-action` for `ghcr.io/${{ github.repository_owner }}/<image>` with tags `type=ref,event=branch` (→ `latest` handled via `type=raw,value=latest,enable={{is_default_branch}}`), `type=semver,pattern={{version}}`, and `type=sha`
- [x] 2.4 `docker/build-push-action`: `context`/`file` from the matrix, `platforms: linux/amd64`, `push: ${{ github.event_name != 'pull_request' }}`, `tags`/`labels` from metadata, `cache-from: type=gha,scope=<name>` and `cache-to: type=gha,mode=max,scope=<name>`

## 3. Validation

- [x] 3.1 Lint the workflow YAML (e.g. `actionlint` or a YAML parse) — parses clean, triggers and permissions present
- [x] 3.2 Confirm the `mcp` build resolves the upstream `obsidian-web-mcp` git pin over https with no extra credential (it is a public repo; the build needs only outbound network)
- [x] 3.3 Confirm PR semantics: on `pull_request` the login step is skipped and `push` is `false` (build-only)
- [x] 3.4 `openspec validate container-build-workflow --strict`
- [x] 3.5 (After a remote exists) dry-run by opening a PR and confirming both matrix legs build green; push to `main` and confirm both images appear in GHCR tagged `latest` + SHA — verified live: created `jjsmackay/obsidian-git-sync-mcp` (public), pushed `main`, run `27954499404` green on both matrix legs, images in GHCR tagged `latest` + `sha-d7b7ea1`. (PR build-only path verified by the `event_name != 'pull_request'` gating, not a separate PR.)
