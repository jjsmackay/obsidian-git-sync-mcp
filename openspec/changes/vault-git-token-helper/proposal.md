## Why

Today the push credential is embedded directly in the vault's remote URL
(`https://x-access-token:<TOKEN>@github.com/...`), so the token lives in plaintext
inside `.git/config` and appears on the `git remote` argv. That is the exact
surface that leaked in production: rotating it means hand-editing a file inside a
named volume, and any tool that echoes the remote (or the config) discloses the
secret. A self-hostable, public-facing image needs a credential path where the
token is supplied at git-invocation time from a single environment variable and
never written to disk or passed on a command line.

## What Changes

- Add a `VAULT_GIT_TOKEN` environment variable as the canonical place to supply
  the push credential.
- Configure git to obtain the credential from a small **env-reading credential
  helper** at fetch/push time. The token is read from the process environment by
  the helper; it is never written to `.git/config` and never appears in argv.
- The remote URL is stored **tokenless** (`https://github.com/<owner>/<repo>.git`).
  When `VAULT_GIT_TOKEN` is set, the worker no longer constructs or persists a
  token-bearing URL.
- `validate_gitsync()` accounts for the new credential path: an HTTPS remote that
  requires authentication with no resolvable credential fails closed at startup
  (consistent with the existing fail-closed contract), rather than failing later
  with an opaque push error.
- Rotation becomes a single-variable operation: change `VAULT_GIT_TOKEN` and
  restart; no surgery inside the vault volume.
- Backward compatibility: a token already embedded in an existing remote URL keeps
  working. `VAULT_GIT_TOKEN` is the recommended path and takes precedence; the
  embedded-URL form is documented as discouraged.

## Capabilities

### New Capabilities
- `git-credential-helper`: an env-reading git credential helper that supplies the
  HTTPS push credential to git at invocation time from `VAULT_GIT_TOKEN`, keeping
  the token out of `.git/config` and out of argv, and making rotation a
  single-variable change.

### Modified Capabilities
- `git-sync-extension`: recognise `VAULT_GIT_TOKEN` as configuration and extend
  the fail-closed `validate_gitsync()` startup check so that an HTTPS remote with
  no resolvable credential refuses to start.

## Impact

- **Config** (`config.py`): new `VAULT_GIT_TOKEN` setting; `validate_gitsync()`
  credential-presence check.
- **Git worker**: tokenless remote-URL handling; ensure the credential helper is
  registered for the git invocations it makes (fetch / rebase / push).
- **Image**: ship the credential-helper entry point and wire it into the repo's
  git configuration during sync setup.
- **Docs / `.env.example`**: document `VAULT_GIT_TOKEN` as the recommended
  credential, and mark the token-in-URL form as discouraged.
- **No requirement change** to commit/push cadence, rebase strategy, or the
  `mcp:`/`sync:` commit split.
