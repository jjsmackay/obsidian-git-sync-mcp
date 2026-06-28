## 1. Fail-closed committer-identity validation

- [x] 1.1 Write failing `validate_gitsync()` tests in `tests/` (matching the existing validate_gitsync style): passes when `VAULT_GIT_GIT_AUTHOR_NAME`/`EMAIL` are set; passes when the host git config resolves an identity and no env identity is set; fails closed (raises `ValueError` naming `VAULT_GIT_GIT_AUTHOR_NAME`/`EMAIL`) when neither resolves — isolating git from host config so the identity is genuinely empty; and remains a no-op when the extension is disabled.
- [x] 1.2 Append the committer-identity check to `validate_gitsync()` in `config.py`: build the `-c user.name=…/-c user.email=…` overrides from `author_name()`/`author_email()` (omitting each when unset) and run `git -C <VAULT_PATH> [overrides] var GIT_AUTHOR_IDENT` via `subprocess.run(check=False)`; on a non-zero exit raise a clear `ValueError` naming the `VAULT_GIT_GIT_AUTHOR_*` remedy. Keep it inside the `is_enabled()` guard and do not echo the resolved identity.

## 2. Verify

- [x] 2.1 Run the full suite — `uv run --extra dev python -m pytest` — all green.
