## 1. Credential helper (env-reading)

- [ ] 1.1 Write failing tests for the helper `main()`: `get` with `VAULT_GIT_TOKEN` set prints `username=x-access-token` + `password=<token>`; `get` with token unset/empty prints nothing and exits 0; `store`/`erase` are no-ops exiting 0. Drive via fake stdin/argv; assert token is read only from env.
- [ ] 1.2 Implement `credential_helper.py` with a `main()` that speaks the git credential-helper protocol per the tests.
- [ ] 1.3 Register the console script `git-credential-obsidian-env = "obsidian_git_sync.credential_helper:main"` in `pyproject.toml` `[project.scripts]`.
- [ ] 1.4 Add a test asserting the installed entry point is on PATH and responds (e.g. `git-credential-obsidian-env get` with the env set), so a broken install fails loudly.

## 2. Config: `VAULT_GIT_TOKEN`

- [ ] 2.1 Write failing tests for a `config.token()` accessor (reads `VAULT_GIT_TOKEN`, stripped; empty → empty) following the `VAULT_GIT_GIT_AUTHOR_*` pattern.
- [ ] 2.2 Implement `VAULT_GIT_TOKEN` env read + `config.token()` accessor in `config.py`.

## 3. Fail-closed validation

- [ ] 3.1 Write failing `validate_gitsync()` tests: tokenless HTTPS push remote + no token → raises, message names the missing credential and does NOT contain the remote URL; HTTPS + token → passes; SSH remote → passes without token; commit-only mode → passes without token; embedded-credential HTTPS URL → passes without token.
- [ ] 3.2 Extend `validate_gitsync()` to parse the already-resolved remote URL (stdlib, no logging) for scheme + embedded userinfo and apply the credential-presence rule.

## 4. Wire the helper into `GitOps` / worker

- [ ] 4.1 Write failing tests that `GitOps` network ops (`fetch`, `push`) include `-c credential.helper=` (clear) followed by `-c credential.helper=<name>` when a helper is configured, and that `commit`/`rebase` do NOT; assert the token value never appears in the constructed argv.
- [ ] 4.2 Add a `credential_helper: str | None` parameter to `GitOps`; prepend the clear+set `-c` args on `fetch`/`push` only. Pass the helper **name** only — never the token.
- [ ] 4.3 Update `GitWorker.from_config()` to pass `credential_helper="obsidian-env"` when `config.token()` is set, else `None`; add a test for both branches.

## 5. Image + docs

- [ ] 5.1 Confirm the credential-helper console script is available on PATH in the built image (it ships with the pip-installed package); add/adjust the Dockerfile only if needed.
- [ ] 5.2 Document `VAULT_GIT_TOKEN` in `.env.example` and the README as the recommended credential; mark the token-in-URL form as discouraged and note the tokenless remote URL + single-variable rotation.

## 6. Verify

- [ ] 6.1 Run the full suite: `uv run --extra dev python -m pytest` — all green.
- [ ] 6.2 Manual sanity (optional, host): with a tokenless HTTPS remote and `VAULT_GIT_TOKEN` set, confirm a push authenticates and the token appears nowhere in `.git/config` or process argv.
