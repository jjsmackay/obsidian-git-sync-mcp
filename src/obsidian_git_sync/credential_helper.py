"""An env-reading git credential helper for the vault's HTTPS push.

git invokes a credential helper as ``git-credential-<name> <action>`` and speaks
its credential protocol on stdin/stdout. This helper sources the credential from
the ``VAULT_GIT_TOKEN`` environment variable, so the token is supplied through one
env var and is never written to ``.git/config`` nor passed on any git argv.

- ``get``  -> when ``VAULT_GIT_TOKEN`` is set, print ``username``/``password``;
             when unset/empty, print nothing and exit 0 so git falls through to
             its normal credential resolution.
- ``store``/``erase`` -> no-op: the token lives only in the environment, so there
             is nothing for git to cache or delete.

The username is fixed to ``x-access-token``: it works for GitHub fine-grained and
classic PATs and installation tokens, and other hosts accept any username with a
PAT as the password over HTTP basic auth.

Wired in as the console script ``git-credential-obsidian-env``; the matching
``credential.helper`` value is ``obsidian-env`` (see ``HELPER_NAME``).
"""

from __future__ import annotations

import os
import sys

# The git ``credential.helper`` value. git resolves it to the executable
# ``git-credential-obsidian-env`` on PATH, so config carries only this name --
# never the secret.
HELPER_NAME = "obsidian-env"

# Fixed basic-auth username; the token is the password. See module docstring.
USERNAME = "x-access-token"


def main(argv: list[str] | None = None) -> int:
    """Entry point. ``argv`` defaults to the process args (the git action first).

    Returns a process exit code (0 always: a missing token is a fall-through, not
    an error). The console-script wrapper passes the return value to ``sys.exit``.
    """
    args = sys.argv[1:] if argv is None else argv
    action = args[0] if args else ""

    # store/erase (and any unknown action) are no-ops -- never cache/delete an
    # env-sourced token.
    if action != "get":
        return 0

    token = os.environ.get("VAULT_GIT_TOKEN", "").strip()
    if not token:
        # No credential to offer; let git resolve credentials as it normally would.
        return 0

    sys.stdout.write(f"username={USERNAME}\n")
    sys.stdout.write(f"password={token}\n")
    return 0
