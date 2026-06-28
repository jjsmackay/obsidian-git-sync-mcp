## Context

Commit identity is injected the idiomatic way: `GitOps._identity_args()`
(`git_ops.py:95–106`) appends `-c user.name=… -c user.email=…` ONLY when an
identity is configured, drawn from `config.author_name()`/`author_email()`
(`config.py:179–186`, reading `VAULT_GIT_GIT_AUTHOR_NAME`/`EMAIL`,
`config.py:70–71`). When those are unset, no overrides are passed and git falls
back to host config (`GIT_AUTHOR_*` env, then system/global/local `user.*`).

`validate_gitsync()` (`config.py:207+`) is the single fail-closed startup check.
It already verifies the vault is a git working tree, parses the sweep/push timing,
and confirms the remote exists with a resolvable credential — each refusing to
boot rather than failing later. It has no committer-identity check, so a vault
with no resolvable identity boots clean and then fails EVERY commit with `rc=128`
("unable to auto-detect email"), silently, per-commit, at runtime.

## Goals / Non-Goals

**Goals:**
- Fail closed at startup when, with the extension enabled, git cannot resolve a
  committer identity.
- Use the SAME identity the worker would: the `-c user.name=…/-c user.email=…`
  overrides from `author_name()`/`author_email()`, or none when those are unset
  (so the check sees exactly what a commit would see).
- A clear `ValueError` naming `VAULT_GIT_GIT_AUTHOR_NAME`/`EMAIL` as the remedy.
- No-op when the extension is disabled.

**Non-Goals:**
- Re-implementing git's identity-resolution precedence in Python.
- A new env var — the check leans on the existing `VAULT_GIT_GIT_AUTHOR_*`.
- Validating that the identity is well-formed (a real name/email); git's own
  acceptance is the bar.

## Decisions

### Ask git, don't reimplement: `git var GIT_AUTHOR_IDENT`

Run `git -C <VAULT_PATH> [-c user.name=…] [-c user.email=…] var GIT_AUTHOR_IDENT`
via `subprocess.run(check=False)`, building the `-c` overrides from
`author_name()`/`author_email()` exactly as the worker does. `git var
GIT_AUTHOR_IDENT` is git's own "resolve the author identity now" probe: it returns
zero with the identity when one is resolvable and exits non-zero (`rc=128`,
"unable to auto-detect email"/"empty ident name") when not — the very failure that
breaks commits. Treat any non-zero exit as unresolvable and fail closed.

Rationale: this is faithful by construction — the check resolves identity through
git with the same inputs the commit will use, so it cannot drift from real
behaviour. Reimplementing the precedence (env → system → global → local) in Python
would duplicate git internals and risk disagreeing with the binary that actually
commits. `git var` is read-only and touches no working-tree state.

### Placement and message

Append the check to `validate_gitsync()` after the existing remote/credential
block, inside the `is_enabled()` guard. The message names the offending config
(`VAULT_GIT_GIT_AUTHOR_NAME`/`EMAIL`) as the remedy. The resolved identity is not
echoed — there is no need; the failure case has no identity, and the success case
returns nothing. (An identity is not a secret, but echoing it adds nothing.)

## Risks / Trade-offs

- **A `git var` invocation at startup** → negligible: one subprocess, read-only,
  same cost as the existing `git remote get-url` check.
- **Host identity present in tests masks the failure path** → the "neither
  resolvable" test must isolate git from host config (point `GIT_CONFIG_GLOBAL`/
  `GIT_CONFIG_SYSTEM` at `/dev/null` and clear `GIT_AUTHOR_*`/`GIT_COMMITTER_*`),
  so the check sees a genuinely empty identity.
- **Future env-only commit path** → if the worker ever passed identity via `env=`
  instead of `-c`, the check would need to mirror that. Today both read the same
  `author_name()`/`author_email()`, so they stay in lockstep.

## Migration Plan

Pure additive validation. A correctly configured deployment (env identity set, or
a host identity) is unaffected and boots as before. A deployment that was silently
dropping commits now fails fast at startup with a clear remedy — the intended
behaviour change. Rollback is reverting the appended check; no state migration.
