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
import subprocess

# Single enabling flag for the whole extension. Empty/unset = disabled (the default).
# Kept as a raw string and parsed in is_enabled() so an unrecognised value fails
# closed (treated as disabled) rather than crashing at import.
#
#   VAULT_GITSYNC_ENABLED -- "true"/"1"/"yes"/"on" enables; anything else disables.
VAULT_GITSYNC_ENABLED = os.environ.get("VAULT_GITSYNC_ENABLED", "")

# Interval (seconds) between periodic sweep events. The sweep is load-bearing, not a
# backstop: the .md watcher is blind to attachments/canvas, so the timer is the only
# thing that catches those. Kept as a raw string and parsed in validate_gitsync() /
# sweep_interval() so a typo fails closed at startup rather than at import.
#
#   VAULT_GITSYNC_SWEEP_INTERVAL -- positive integer seconds (default 60).
VAULT_GITSYNC_SWEEP_INTERVAL = os.environ.get("VAULT_GITSYNC_SWEEP_INTERVAL", "60")

# The git remote to push to. Default "origin"; an EMPTY string selects commit-only
# mode (a purely local audit trail / backup-to-disk, never a push). Kept raw and
# parsed in remote() / checked in validate_gitsync() so a missing remote fails
# closed at startup rather than on the first push.
#
#   VAULT_GITSYNC_REMOTE -- remote name, or "" for commit-only (default "origin").
VAULT_GITSYNC_REMOTE = os.environ.get("VAULT_GITSYNC_REMOTE", "origin")

# The branch to push. EMPTY = use the working tree's current branch (resolved at
# worker start). Set it explicitly only to pin a branch other than HEAD.
#
#   VAULT_GITSYNC_BRANCH -- branch name, or "" to use the current branch (default "").
VAULT_GITSYNC_BRANCH = os.environ.get("VAULT_GITSYNC_BRANCH", "")

# Push debounce: seconds the event queue must stay quiet before the worker pushes
# the commits it has accumulated. Decouples granular per-event commits from
# batched pushes. Kept raw, parsed in push_debounce() / checked in validate.
#
#   VAULT_GITSYNC_PUSH_DEBOUNCE -- positive number of seconds (default 10).
VAULT_GITSYNC_PUSH_DEBOUNCE = os.environ.get("VAULT_GITSYNC_PUSH_DEBOUNCE", "10")

# Push max interval: an upper bound (seconds) on time-since-last-push so a queue
# that never goes quiet under sustained load still pushes periodically.
#
#   VAULT_GITSYNC_PUSH_MAX_INTERVAL -- positive number of seconds (default 300).
VAULT_GITSYNC_PUSH_MAX_INTERVAL = os.environ.get("VAULT_GITSYNC_PUSH_MAX_INTERVAL", "300")

# Optional commit author identity. When set, the worker commits with this name/
# email via ``git -c user.name=… -c user.email=…`` so commits carry a stable
# author without depending on the host's global git config. Empty = let git use
# whatever identity the host configures.
#
#   VAULT_GITSYNC_GIT_AUTHOR_NAME / VAULT_GITSYNC_GIT_AUTHOR_EMAIL -- optional.
VAULT_GITSYNC_GIT_AUTHOR_NAME = os.environ.get("VAULT_GITSYNC_GIT_AUTHOR_NAME", "")
VAULT_GITSYNC_GIT_AUTHOR_EMAIL = os.environ.get("VAULT_GITSYNC_GIT_AUTHOR_EMAIL", "")

# Optional push heartbeat. When set, the worker GETs this URL after each
# successful push so a push-style monitor sees git sync reached the remote.
# EMPTY = disabled (the default). Kept raw and parsed/validated in
# validate_gitsync() so a malformed URL fails closed at startup. The value may be
# a capability URL (secret in the path), so it is never echoed in errors/logs.
#
#   VAULT_GITSYNC_HEARTBEAT_URL -- an http(s) URL with a host, or "" to disable.
VAULT_GITSYNC_HEARTBEAT_URL = os.environ.get("VAULT_GITSYNC_HEARTBEAT_URL", "")

# Frontmatter stamping toggle. Unlike the extension's master switch this defaults
# ENABLED ("" => on): stamping is the project's reason for existing, so the safe
# default is to stamp. Operators who do not use timestamp frontmatter set this to
# a falsey value and MCP-written files are committed exactly as the client sent
# them. Kept raw and parsed in stamp_enabled() so an unrecognised value is treated
# as enabled (the default) rather than crashing at import.
#
#   VAULT_GITSYNC_STAMP -- a falsey string ("0"/"false"/"no"/"off") disables;
#   anything else (including unset) enables.
VAULT_GITSYNC_STAMP = os.environ.get("VAULT_GITSYNC_STAMP", "")

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}


def _is_truthy(raw: str, *, default: bool) -> bool:
    """Parse a raw env string to a bool, falling back to ``default``.

    Recognises the same truthy/falsey vocabularies project-wide. ``default`` is
    returned for the empty string and any unrecognised value, so each flag can
    choose whether ambiguity fails on or off.
    """
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSEY:
        return False
    return default


def is_enabled() -> bool:
    """Return whether the git-sync extension is enabled.

    Defaults to False. Only the recognised truthy strings enable it; everything
    else (including unrecognised values) is treated as disabled so an unclear
    setting fails to the safe no-op state.
    """
    return _is_truthy(VAULT_GITSYNC_ENABLED, default=False)


def stamp_enabled() -> bool:
    """Return whether frontmatter stamping is enabled (default True).

    Reuses the same truthy/falsey parsing as ``is_enabled()`` but defaults ON: a
    falsey ``VAULT_GITSYNC_STAMP`` opts out, an unset or unrecognised value stamps.
    """
    return _is_truthy(VAULT_GITSYNC_STAMP, default=True)


def sweep_interval() -> int:
    """Return the periodic-sweep interval in seconds.

    Parses ``VAULT_GITSYNC_SWEEP_INTERVAL`` -- call only after ``validate_gitsync()``
    has accepted it (validation is where a bad value fails closed).
    """
    return int(VAULT_GITSYNC_SWEEP_INTERVAL)


def remote() -> str:
    """Return the configured remote name, or "" for commit-only mode.

    Stripped so trailing whitespace from an env file is not mistaken for a remote.
    """
    return VAULT_GITSYNC_REMOTE.strip()


def branch() -> str:
    """Return the configured branch, or "" to mean "use the current branch"."""
    return VAULT_GITSYNC_BRANCH.strip()


def push_debounce() -> float:
    """Return the push-debounce window in seconds.

    Parses ``VAULT_GITSYNC_PUSH_DEBOUNCE`` -- call only after ``validate_gitsync()``
    has accepted it.
    """
    return float(VAULT_GITSYNC_PUSH_DEBOUNCE)


def push_max_interval() -> float:
    """Return the maximum interval (seconds) between pushes under load.

    Parses ``VAULT_GITSYNC_PUSH_MAX_INTERVAL`` -- call only after validation.
    """
    return float(VAULT_GITSYNC_PUSH_MAX_INTERVAL)


def author_name() -> str | None:
    """The configured commit author name, or None when unset."""
    return VAULT_GITSYNC_GIT_AUTHOR_NAME.strip() or None


def author_email() -> str | None:
    """The configured commit author email, or None when unset."""
    return VAULT_GITSYNC_GIT_AUTHOR_EMAIL.strip() or None


def heartbeat_url() -> str:
    """Return the configured push-heartbeat URL, or "" when disabled.

    Stripped so trailing whitespace from an env file is not mistaken for a URL.
    Call only after ``validate_gitsync()`` has accepted it.
    """
    return VAULT_GITSYNC_HEARTBEAT_URL.strip()


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

    # Parse-and-check the sweep interval here (mirroring upstream validate_heartbeat):
    # a non-integer or non-positive value must refuse to boot rather than tight-loop
    # or crash later when the timer first reads it.
    try:
        interval = int(VAULT_GITSYNC_SWEEP_INTERVAL)
    except ValueError:
        raise ValueError(
            "VAULT_GITSYNC_SWEEP_INTERVAL must be an integer number of seconds"
        )
    if interval <= 0:
        raise ValueError("VAULT_GITSYNC_SWEEP_INTERVAL must be a positive integer")

    # Push timing: both must be positive numbers. A non-positive debounce would
    # tight-loop the worker; a non-positive max-interval would force a push every
    # cycle. Parse-and-check here so either fails closed at startup.
    for name, raw in (
        ("VAULT_GITSYNC_PUSH_DEBOUNCE", VAULT_GITSYNC_PUSH_DEBOUNCE),
        ("VAULT_GITSYNC_PUSH_MAX_INTERVAL", VAULT_GITSYNC_PUSH_MAX_INTERVAL),
    ):
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f"{name} must be a number of seconds")
        if value <= 0:
            raise ValueError(f"{name} must be a positive number of seconds")

    # When a remote is configured (the default), it must actually exist in the
    # working tree -- a misconfigured remote that fails only on the first push is
    # a worse failure mode than refusing to boot. Commit-only mode (REMOTE="")
    # skips this check. Checked via ``git remote get-url``; never echo the URL.
    remote_name = remote()
    if remote_name:
        result = subprocess.run(
            ["git", "-C", str(VAULT_PATH), "remote", "get-url", remote_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(
                f"git-sync is enabled but VAULT_GITSYNC_REMOTE '{remote_name}' "
                f"does not exist in the vault at VAULT_PATH"
            )

    # Optional push heartbeat. Empty = disabled (valid). When set, it must be an
    # http(s) URL with a host, mirroring upstream validate_heartbeat (incl. the
    # port-parse so a malformed port fails closed). The URL is a capability URL
    # (secret in the path), so the messages name only the var, never the value.
    hb_url = heartbeat_url()
    if hb_url:
        from urllib.parse import urlsplit

        try:
            parsed = urlsplit(hb_url)
            port = parsed.port  # raises ValueError on a malformed port
        except ValueError:
            raise ValueError("VAULT_GITSYNC_HEARTBEAT_URL has a malformed port")
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            raise ValueError(
                "VAULT_GITSYNC_HEARTBEAT_URL must be an http(s) URL with a host"
            )
        del port  # only accessed to trigger the malformed-port check
