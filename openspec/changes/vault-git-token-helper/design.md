## Context

All git work runs through one method, `GitOps._run()` (`git_ops.py:68–87`):
`subprocess.run(["git", "-C", <vault>, *args], …)` with **no `env=`** (so git
inherits the worker's environment) and **no credential configuration**. Commit
identity is already injected the idiomatic way — `-c user.name=… -c user.email=…`
appended only on `commit()` (`git_ops.py:89–100,143`). Authentication today relies
entirely on a credential embedded in the remote URL inside `.git/config`, which is
exactly what leaked: it sits in plaintext on disk and on the `git remote` argv,
and rotation means editing a file inside a named volume.

Config follows a strict `VAULT_GIT_*` convention, parsed lazily, with a
fail-closed `validate_gitsync()` that already runs `git remote get-url <remote>`
to confirm the remote exists — **without ever echoing the URL** (`config.py:249–265`).

## Goals / Non-Goals

**Goals:**
- Supply the push credential from one env var, `VAULT_GIT_TOKEN`, read at git
  invocation time.
- Token never written to `.git/config`; never present in any git argv.
- Rotation = change the env var and restart. No volume surgery.
- Fail closed at startup when an HTTPS push remote has no resolvable credential.
- Backward compatible: an embedded-credential URL keeps working.

**Non-Goals:**
- Per-host or multi-credential support; one token, one remote.
- A configurable username (fixed `x-access-token`; see Decisions). A
  `VAULT_GIT_USERNAME` override is a trivial future add, not in this change.
- Rewriting an existing token-bearing remote URL to a tokenless one (that is a
  bootstrap/setup concern; here the URL is assumed already tokenless when a token
  is used). Docs flag the embedded form as discouraged.
- SSH credential handling (keys already work via the inherited environment).

## Decisions

### A native git credential helper, named, on PATH

Implement the helper as a console script `git-credential-obsidian-env`
(`[project.scripts]` → `obsidian_git_sync.credential_helper:main`). Git's
convention means a `credential.helper` value of `obsidian-env` resolves to the
`git-credential-obsidian-env` executable on `PATH` — so configuration carries only
the **helper name**, never the secret. The package is pip-installed in the image
and in the test env (`uv run --extra dev`), so the script is on `PATH` in both.

The helper speaks the credential-helper protocol on stdin/stdout:
- `get` → if `VAULT_GIT_TOKEN` is non-empty, print `username=x-access-token` and
  `password=<token>`; otherwise print nothing and exit 0 (git falls through).
- `store` / `erase` → no-op, exit 0 (never cache or delete an env-sourced token).

Rationale: this is the only approach where the token value touches **neither**
`.git/config` **nor** argv. The token lives solely in the process environment and
is read by the helper subprocess (which inherits that environment). Compared with
the alternatives below, it is the most git-idiomatic and the easiest to unit-test
(drive `main()` with a fake stdin).

### Wire the helper per-invocation, not via persisted config

`GitOps` gains a `credential_helper: str | None` parameter (the helper name, e.g.
`"obsidian-env"`). When set, **network** operations — `fetch` and `push` — are run
with `-c credential.helper= -c credential.helper=<name>` prepended (the empty
value first **clears** any inherited system/global helper, then ours is set).
Non-network operations (`commit`, `rebase`) are untouched.

`GitOps` is given the helper **name only**, never the token value — so even the
Python layer never holds the secret in a place that could reach argv. The token is
read exclusively by the helper subprocess from the inherited environment;
`subprocess.run` already passes the parent environment through (no `env=` needed).

`GitWorker.from_config()` passes `credential_helper="obsidian-env"` when
`config.token()` is set, else `None` (preserving today's behaviour exactly).

Rationale: per-invocation `-c` keeps the change self-contained and stateless — no
mutation of the vault's `.git/config`, nothing for bootstrap to set up or undo,
and it composes with the existing identity-injection pattern.

### `validate_gitsync()` credential-presence check

Extend the existing remote check. After resolving the remote URL (already done,
not logged), when in push mode:
- URL scheme `https`/`http` **and** no embedded credential (no `userinfo@` in the
  authority) **and** `VAULT_GIT_TOKEN` empty → **fail closed** with a message that
  names the missing credential but does **not** include the URL.
- SSH URL, embedded-credential URL, or commit-only mode → no token required.

Rationale: converts an opaque later `push` failure (`rc=128`) into a clear startup
error, consistent with the fail-closed contract.

## Risks / Trade-offs

- **`x-access-token` username generality.** Works for GitHub fine-grained/classic
  PATs and installation tokens; GitLab/Gitea accept any username with a PAT as
  password over HTTP basic, so it is broadly safe. If a host ever rejects it, the
  fix is the deferred `VAULT_GIT_USERNAME` override — cheap to add later.
- **Inherited-helper suppression.** Prepending an empty `credential.helper`
  neutralises a host-level helper for our invocations only; it does not alter the
  vault config. Low risk, and scoped to fetch/push.
- **Helper must be on PATH.** If the console script is missing (broken install),
  git gets no credential and push fails — surfaced as the existing logged push
  failure, and caught earlier by the startup credential check when the token is
  set. A test asserts the entry point is installed and responds.
- **Scheme detection in validation.** Parsing the remote URL for scheme/userinfo
  must stay silent (never log the URL). Use stdlib URL parsing on the already
  in-hand string; no new exposure surface.
- **Backward-compat overlap.** If both an embedded-URL credential and
  `VAULT_GIT_TOKEN` are present, the env helper supplies credentials but git may
  prefer the URL's userinfo. This is a discouraged misconfiguration; docs tell
  operators to use a tokenless URL with `VAULT_GIT_TOKEN`. No special handling.
