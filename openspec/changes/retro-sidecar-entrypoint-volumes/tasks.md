## 1. Entry-point dispatch (obsidian-sync-sidecar)

- [x] 1.1 Record the explicit-only bootstrap (`bootstrap` arg / `BOOTSTRAP` env), forwarding remaining args (e.g. `--reset`) — already in `obsidian-sync/entrypoint.sh`
- [x] 1.2 Record the passthrough escape hatch: any other explicit command exec'd verbatim — already shipped
- [x] 1.3 Record the four-way no-command start decision (bootstrap / verbatim / sync-if-bootstrapped / idle-and-poll) — already shipped
- [x] 1.4 Record the no-auto-on-TTY rationale (compose `tty: true` would hang at `ob login`) — already shipped
- [x] 1.5 Do NOT restate the already-spec'd idle auto-start poll or `bootstrap --reset` requirements

## 2. Config named-volume ownership (obsidian-sync-sidecar)

- [x] 2.1 Record that the image pre-creates `/home/ob/.config/obsidian-headless` as uid 10001 before the mount so a fresh `config` volume inherits `ob` ownership — already in `obsidian-sync/Dockerfile`
- [x] 2.2 Confirm `docker-compose.yml` mounts the `config` named volume at that path — already shipped

## 3. Vault named-volume ownership (container-deployment)

- [x] 3.1 Record that a fresh named vault volume mounts root-owned and must be seeded + `chown -R 10001:10001`'d for the uid-10001 user to commit — already in `README.md`
- [x] 3.2 Record that the vault volume has no image-side fix (unlike the `config` volume) — already documented

## 4. Docs: commit identity, ordering, re-bootstrap (docs)

- [x] 4.1 Record the worker commit-identity requirement and the two ways to set it (`VAULT_GIT_GIT_AUTHOR_*` or vault git config) — already in `README.md`
- [x] 4.2 Record the git-tree-first / `ob`-bootstrap ordering and the pre-sync credential note — already in `README.md`
- [x] 4.3 Record the `bootstrap --reset` re-bootstrap path — already in `obsidian-sync/README.md`

## 5. Validation

- [x] 5.1 Confirm the current files match what is spec'd (no code/Dockerfile/compose/shell/README edits needed)
- [x] 5.2 `openspec validate --all` passes
- [x] 5.3 No Python logic changed; `uv run --extra dev python -m pytest` stays green (124 passed)
