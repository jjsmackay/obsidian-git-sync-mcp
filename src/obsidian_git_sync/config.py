"""Configuration for the git-sync extension, read from ``VAULT_GITSYNC_*`` env vars.

Mirrors the upstream ``obsidian_vault_mcp.config`` idiom: values are read as raw
strings at module import via ``os.environ.get`` and parsed/validated lazily in a
``validate_*`` function that raises ``ValueError``. Keeping parsing in the validator
(not at import) means a typo fails CLOSED at startup with a clear message rather than
crashing on import or, worse, booting a half-configured sync.

The extension is DISABLED by default: nothing runs and no validation is enforced
unless ``VAULT_GITSYNC_ENABLED`` is set to a truthy value. This is the safe failure
mode for a backup/sync add-on shipped into the upstream image -- it must be a no-op
until an operator deliberately turns it on.

Variable names are provisional and reconciled with ``.env.example`` in the
container-deployment change.
"""

import os

# Single enabling flag for the whole extension. Empty/unset = disabled (the default).
# Kept as a raw string and parsed in is_enabled() so an unrecognised value fails
# closed (treated as disabled) rather than crashing at import.
#
#   VAULT_GITSYNC_ENABLED -- "true"/"1"/"yes"/"on" enables; anything else disables.
VAULT_GITSYNC_ENABLED = os.environ.get("VAULT_GITSYNC_ENABLED", "")

_TRUTHY = {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    """Return whether the git-sync extension is enabled.

    Defaults to False. Only the recognised truthy strings enable it; everything
    else (including unrecognised values) is treated as disabled so an unclear
    setting fails to the safe no-op state.
    """
    return VAULT_GITSYNC_ENABLED.strip().lower() in _TRUTHY


def validate_gitsync() -> None:
    """Validate git-sync configuration at startup; raise ``ValueError`` if invalid.

    A no-op when the extension is disabled -- the disabled case must never abort
    startup. When enabled, this is the single fail-closed check: a misconfigured
    backup that looks healthy until the first write is a worse failure mode than
    refusing to boot, so we verify the essentials up front.

    For this scaffold the meaningful check is that the vault the upstream server
    operates on (``VAULT_PATH``) exists and is a git working tree -- git sync has
    nothing to commit against otherwise. Later changes add remote/branch checks.

    Messages name the offending configuration and never echo secrets.
    """
    if not is_enabled():
        return

    # Imported lazily: the upstream config reads VAULT_PATH at import, and tests
    # set it on the module after import -- a top-level import would bind a stale value.
    from obsidian_vault_mcp.config import VAULT_PATH

    if not VAULT_PATH.is_dir():
        raise ValueError(
            f"git-sync is enabled but VAULT_PATH does not exist or is not a "
            f"directory: {VAULT_PATH}"
        )

    # A git working tree has a .git entry at its root (a dir for a normal clone,
    # a file for a worktree/submodule). Either is acceptable.
    if not (VAULT_PATH / ".git").exists():
        raise ValueError(
            f"git-sync is enabled but VAULT_PATH is not a git working tree (no "
            f".git found): {VAULT_PATH}"
        )
