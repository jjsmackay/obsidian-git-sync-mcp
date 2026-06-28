## Why

The worker commits with `git -c user.name=… -c user.email=…` only when
`VAULT_GIT_GIT_AUTHOR_NAME`/`EMAIL` are set; otherwise git falls back to the host
config. When neither the env identity nor host git config resolves BOTH name and
email, every commit fails with `rc=128` ("unable to auto-detect email") —
silently, per-commit, at runtime. A backup that boots healthy and then drops every
commit is a worse failure mode than refusing to start, and it violates the
project's fail-closed contract.

## What Changes

- Extend `validate_gitsync()` so that, when the extension is enabled, it verifies
  git can resolve a committer identity up front and fails closed otherwise.
- The check asks git itself, using the SAME identity overrides the worker applies:
  `git -C <VAULT_PATH> [-c user.name=…] [-c user.email=…] var GIT_AUTHOR_IDENT`
  (overrides drawn from `config.author_name()`/`author_email()`). A non-zero exit
  means no identity is resolvable.
- On failure, raise a clear `ValueError` naming `VAULT_GIT_GIT_AUTHOR_NAME` and
  `VAULT_GIT_GIT_AUTHOR_EMAIL` as the remedy. The resolved identity is not echoed
  beyond what a clear message needs.
- No-op when the extension is disabled (consistent with the rest of the validator).

## Capabilities

### Modified Capabilities
- `git-sync-extension`: add a fail-closed `validate_gitsync()` startup requirement
  that an unresolvable committer identity refuses to start, alongside the existing
  remote/credential fail-closed checks.

## Impact

- **Config** (`config.py`): a committer-identity check appended to
  `validate_gitsync()`, reusing `author_name()`/`author_email()`. No new env var
  (it leans on the existing `VAULT_GIT_GIT_AUTHOR_*`).
- **Tests** (`tests/`): coverage for env identity set, host-config identity,
  neither resolvable (fails closed), and disabled no-op.
- **No behaviour change** to commit/push cadence, the worker's identity injection,
  or the `mcp:`/`sync:` commit split.
