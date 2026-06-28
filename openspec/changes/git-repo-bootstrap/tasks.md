## 1. Image

- [x] 1.1 Add `openssh-client` to the mcp `Dockerfile` apt install (git's SSH transport needs an `ssh` binary; it is only a Recommends of `git` and was dropped by `--no-install-recommends`)

## 2. Compose

- [x] 2.1 Replace the prose credential comments on the `mcp` service with a concrete, opt-in SSH deploy-key mount + `GIT_SSH_COMMAND` block (commented out by default)
- [x] 2.2 Document that the token-in-https-URL path needs no mount (credential lives in the vault's `.git/config`)
- [x] 2.3 Note on the vault volume that an unseeded tree fails closed once git sync is enabled

## 3. Docs

- [x] 3.1 README "Git repo bootstrap" section: fail-closed precondition up front, then clone → credential choice → enable
- [x] 3.2 Document both credential mechanisms (token-in-https-URL recommended; SSH deploy key)
- [x] 3.3 Ordering note versus the obsidian-sync sidecar bootstrap

## 4. Validation

- [x] 4.1 `docker-compose.yml` is valid YAML and the credential mount/`environment` stay commented (opt-in)
- [x] 4.2 No Python logic changed; `uv run --extra dev python -m pytest` stays green (102 passed)
