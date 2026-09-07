"""Configuration for the git-sync extension, read from ``VAULT_GIT_*`` env vars.

One exception: ``VAULT_MCP_EXTENSIONS`` (which extensions this package's entry
point loads) is a server-host concern in the upstream namespace, not a git-sync
setting. It lives here to keep every env read in one module; see its own comment.

Mirrors the upstream ``obsidian_vault_mcp.config`` idiom: values are read as raw
strings at module import via ``os.environ.get`` and parsed/validated lazily in a
``validate_*`` function that raises ``ValueError``. Keeping parsing in the validator
(not at import) means a typo fails CLOSED at startup with a clear message rather than
crashing on import or, worse, booting a half-configured sync.

The extension is DISABLED by default: nothing runs and no validation is enforced
unless ``VAULT_GIT_ENABLED`` is set to a truthy value. This is the safe failure
mode for a backup/sync add-on shipped into the upstream image -- it must be a no-op
until an operator deliberately turns it on.

Variable names are provisional and reconciled with ``.env.example`` in the
container-deployment change.
"""

import importlib
import os
import subprocess
from urllib.parse import urlsplit

# Single enabling flag for the whole extension. Empty/unset = disabled (the default).
# Kept as a raw string and parsed in is_enabled() so an unrecognised value fails
# closed (treated as disabled) rather than crashing at import.
#
#   VAULT_GIT_ENABLED -- "true"/"1"/"yes"/"on" enables; anything else disables.
VAULT_GIT_ENABLED = os.environ.get("VAULT_GIT_ENABLED", "")

# Interval (seconds) between periodic sweep events. The sweep is load-bearing, not a
# backstop: the .md watcher is blind to attachments/canvas, so the timer is the only
# thing that catches those. Kept as a raw string and parsed in validate_gitsync() /
# sweep_interval() so a typo fails closed at startup rather than at import.
#
#   VAULT_GIT_SWEEP_INTERVAL -- positive integer seconds (default 60).
VAULT_GIT_SWEEP_INTERVAL = os.environ.get("VAULT_GIT_SWEEP_INTERVAL", "60")

# The git remote to push to. Default "origin"; an EMPTY string selects commit-only
# mode (a purely local audit trail / backup-to-disk, never a push). Kept raw and
# parsed in remote() / checked in validate_gitsync() so a missing remote fails
# closed at startup rather than on the first push.
#
#   VAULT_GIT_REMOTE -- remote name, or "" for commit-only (default "origin").
VAULT_GIT_REMOTE = os.environ.get("VAULT_GIT_REMOTE", "origin")

# The branch to push. EMPTY = use the working tree's current branch (resolved at
# worker start). Set it explicitly only to pin a branch other than HEAD.
#
#   VAULT_GIT_BRANCH -- branch name, or "" to use the current branch (default "").
VAULT_GIT_BRANCH = os.environ.get("VAULT_GIT_BRANCH", "")

# Push debounce: seconds the event queue must stay quiet before the worker pushes
# the commits it has accumulated. Decouples granular per-event commits from
# batched pushes. Kept raw, parsed in push_debounce() / checked in validate.
#
#   VAULT_GIT_PUSH_DEBOUNCE -- positive number of seconds (default 10).
VAULT_GIT_PUSH_DEBOUNCE = os.environ.get("VAULT_GIT_PUSH_DEBOUNCE", "10")

# Push max interval: an upper bound (seconds) on time-since-last-push so a queue
# that never goes quiet under sustained load still pushes periodically.
#
#   VAULT_GIT_PUSH_MAX_INTERVAL -- positive number of seconds (default 300).
VAULT_GIT_PUSH_MAX_INTERVAL = os.environ.get("VAULT_GIT_PUSH_MAX_INTERVAL", "300")

# Optional commit author identity. When set, the worker commits with this name/
# email via ``git -c user.name=… -c user.email=…`` so commits carry a stable
# author without depending on the host's global git config. Empty = let git use
# whatever identity the host configures.
#
#   VAULT_GIT_GIT_AUTHOR_NAME / VAULT_GIT_GIT_AUTHOR_EMAIL -- optional.
VAULT_GIT_GIT_AUTHOR_NAME = os.environ.get("VAULT_GIT_GIT_AUTHOR_NAME", "")
VAULT_GIT_GIT_AUTHOR_EMAIL = os.environ.get("VAULT_GIT_GIT_AUTHOR_EMAIL", "")

# Optional push heartbeat. When set, the worker GETs this URL after each
# successful push so a push-style monitor sees git sync reached the remote.
# EMPTY = disabled (the default). Kept raw and parsed/validated in
# validate_gitsync() so a malformed URL fails closed at startup. The value may be
# a capability URL (secret in the path), so it is never echoed in errors/logs.
#
#   VAULT_GIT_HEARTBEAT_URL -- an http(s) URL with a host, or "" to disable.
VAULT_GIT_HEARTBEAT_URL = os.environ.get("VAULT_GIT_HEARTBEAT_URL", "")

# Frontmatter stamping toggle. Unlike the extension's master switch this defaults
# ENABLED ("" => on): stamping is the project's reason for existing, so the safe
# default is to stamp. Operators who do not use timestamp frontmatter set this to
# a falsey value and MCP-written files are committed exactly as the client sent
# them. Kept raw and parsed in stamp_enabled() so an unrecognised value is treated
# as enabled (the default) rather than crashing at import.
#
#   VAULT_GIT_STAMP -- a falsey string ("0"/"false"/"no"/"off") disables;
#   anything else (including unset) enables.
VAULT_GIT_STAMP = os.environ.get("VAULT_GIT_STAMP", "")

# Optional HTTPS push credential. When set, it is supplied to git at invocation
# time by the env-reading credential helper (credential_helper.py) so the token is
# never written to .git/config nor passed on a git argv. EMPTY = no token (the
# credential is resolved by git as usual, e.g. an SSH key or a URL-embedded token).
# Kept raw and read in token(); never echoed in errors/logs (it is a secret).
#
#   VAULT_GIT_TOKEN -- the HTTPS push token, or "" for none (default "").
VAULT_GIT_TOKEN = os.environ.get("VAULT_GIT_TOKEN", "")

# Additional extensions the operator wants this entry point to load alongside
# GitSyncExtension, as a comma-separated list of ``module.path:ClassName`` import
# specs. EMPTY/unset = none, and then no import machinery runs at all.
#
# Deliberately in the upstream ``VAULT_MCP_*`` namespace rather than this package's
# ``VAULT_GIT_*``: it configures the SERVER HOST (which extensions the process
# runs), not git sync, and a git-prefixed name for "load an unrelated extension"
# would mislead. This package defines the name until upstream defines it; if
# upstream ever ships extension composition itself, this variable is deleted
# rather than reconciled.
#
# Kept raw and resolved in extra_extensions() so a typo fails CLOSED at startup
# rather than at import or, worse, boots a server missing the extension an
# operator asked for.
#
#   VAULT_MCP_EXTENSIONS -- "pkg.mod:Class,other.mod:Class", or "" for none.
VAULT_MCP_EXTENSIONS = os.environ.get("VAULT_MCP_EXTENSIONS", "")

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
    return _is_truthy(VAULT_GIT_ENABLED, default=False)


def stamp_enabled() -> bool:
    """Return whether frontmatter stamping is enabled (default True).

    Reuses the same truthy/falsey parsing as ``is_enabled()`` but defaults ON: a
    falsey ``VAULT_GIT_STAMP`` opts out, an unset or unrecognised value stamps.
    """
    return _is_truthy(VAULT_GIT_STAMP, default=True)


def sweep_interval() -> int:
    """Return the periodic-sweep interval in seconds.

    Parses ``VAULT_GIT_SWEEP_INTERVAL`` -- call only after ``validate_gitsync()``
    has accepted it (validation is where a bad value fails closed).
    """
    return int(VAULT_GIT_SWEEP_INTERVAL)


def remote() -> str:
    """Return the configured remote name, or "" for commit-only mode.

    Stripped so trailing whitespace from an env file is not mistaken for a remote.
    """
    return VAULT_GIT_REMOTE.strip()


def branch() -> str:
    """Return the configured branch, or "" to mean "use the current branch"."""
    return VAULT_GIT_BRANCH.strip()


def push_debounce() -> float:
    """Return the push-debounce window in seconds.

    Parses ``VAULT_GIT_PUSH_DEBOUNCE`` -- call only after ``validate_gitsync()``
    has accepted it.
    """
    return float(VAULT_GIT_PUSH_DEBOUNCE)


def push_max_interval() -> float:
    """Return the maximum interval (seconds) between pushes under load.

    Parses ``VAULT_GIT_PUSH_MAX_INTERVAL`` -- call only after validation.
    """
    return float(VAULT_GIT_PUSH_MAX_INTERVAL)


def author_name() -> str | None:
    """The configured commit author name, or None when unset."""
    return VAULT_GIT_GIT_AUTHOR_NAME.strip() or None


def author_email() -> str | None:
    """The configured commit author email, or None when unset."""
    return VAULT_GIT_GIT_AUTHOR_EMAIL.strip() or None


def token() -> str:
    """Return the configured HTTPS push token, or "" when none is set.

    Stripped so trailing whitespace from an env file is not mistaken for a token.
    The value is a secret -- callers must never log it.
    """
    return VAULT_GIT_TOKEN.strip()


def heartbeat_url() -> str:
    """Return the configured push-heartbeat URL, or "" when disabled.

    Stripped so trailing whitespace from an env file is not mistaken for a URL.
    Call only after ``validate_gitsync()`` has accepted it.
    """
    return VAULT_GIT_HEARTBEAT_URL.strip()


def _resolve_extension(spec: str):
    """Resolve one ``module.path:ClassName`` spec to an ``Extension`` subclass.

    Raises ``ValueError`` naming the offending spec for every rejection -- a
    malformed spec, an unimportable module, a missing attribute, or a target that
    is not an ``extensions.Extension`` subclass. Never returns a partial result:
    the caller either gets a usable class or an error identifying what was wrong.
    """
    # Imported lazily to keep this module importable without the upstream server
    # (the rest of config.py follows the same rule for VAULT_PATH).
    from obsidian_vault_mcp.extensions import Extension

    prefix = f"VAULT_MCP_EXTENSIONS entry {spec!r}"
    # Strip each half up front: the caller only trimmed the whole entry, so
    # "mod : Class" still needs normalising before it is validated.
    module_path, separator, class_name = (part.strip() for part in spec.partition(":"))
    if not separator or not module_path or not class_name:
        raise ValueError(f"{prefix} is malformed: expected 'module.path:ClassName'")

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ValueError(f"{prefix} names a module that could not be imported: {e}")

    try:
        target = getattr(module, class_name)
    except AttributeError:
        raise ValueError(
            f"{prefix} names {class_name!r}, which module {module_path!r} does not define"
        )

    if not (isinstance(target, type) and issubclass(target, Extension)):
        raise ValueError(
            f"{prefix} resolved to {target!r}, which is not a subclass of "
            f"obsidian_vault_mcp.extensions.Extension"
        )
    return target


def extra_extensions() -> list:
    """Return the operator-declared additional extension classes, in order.

    This IS the startup validation for ``VAULT_MCP_EXTENSIONS``: resolution
    produces the classes the entry point needs and raises ``ValueError`` on any
    bad entry, so there is no separate ``validate_*`` pass to run (one would
    either re-import every declared module or discard its own result).

    Empty when nothing is declared -- an unset, empty, whitespace-only, or
    comma-only value imports nothing at all. Padding and a trailing or repeated
    comma from a hand-edited env file are tolerated rather than rejected.

    Resolution is ALL-OR-NOTHING: one bad entry raises and no class is returned,
    because a server running without the extension an operator asked for is a
    silently wrong deployment.

    Independent of ``is_enabled()`` on purpose -- a declared extension must load
    whether or not git sync itself is turned on.
    """
    return [
        _resolve_extension(spec)
        for spec in (raw.strip() for raw in VAULT_MCP_EXTENSIONS.split(","))
        if spec
    ]


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
        interval = int(VAULT_GIT_SWEEP_INTERVAL)
    except ValueError:
        raise ValueError(
            "VAULT_GIT_SWEEP_INTERVAL must be an integer number of seconds"
        )
    if interval <= 0:
        raise ValueError("VAULT_GIT_SWEEP_INTERVAL must be a positive integer")

    # Push timing: both must be positive numbers. A non-positive debounce would
    # tight-loop the worker; a non-positive max-interval would force a push every
    # cycle. Parse-and-check here so either fails closed at startup.
    for name, raw in (
        ("VAULT_GIT_PUSH_DEBOUNCE", VAULT_GIT_PUSH_DEBOUNCE),
        ("VAULT_GIT_PUSH_MAX_INTERVAL", VAULT_GIT_PUSH_MAX_INTERVAL),
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
                f"git-sync is enabled but VAULT_GIT_REMOTE '{remote_name}' "
                f"does not exist in the vault at VAULT_PATH"
            )

        # Credential presence (fail closed before the first push). An HTTPS remote
        # whose URL carries no embedded credential needs VAULT_GIT_TOKEN (supplied
        # at push time by the credential helper). An SSH remote authenticates by
        # key, and an HTTPS URL that already embeds a credential carries its own --
        # neither needs a token. The URL may embed a secret, so it is parsed but
        # never echoed: the message names only the config vars.
        remote_url = result.stdout.strip()
        parsed = urlsplit(remote_url)
        is_https = parsed.scheme.lower() in ("http", "https")
        has_embedded_credential = bool(parsed.username)
        if is_https and not has_embedded_credential and not token():
            raise ValueError(
                "git-sync is enabled with an HTTPS VAULT_GIT_REMOTE but no push "
                "credential is configured; set VAULT_GIT_TOKEN"
            )

    # Committer identity must be resolvable (fail closed before the first commit).
    # The worker commits with ``-c user.name=…/-c user.email=…`` only when the
    # VAULT_GIT_GIT_AUTHOR_* identity is set; otherwise git falls back to host
    # config. If neither resolves BOTH name and email, every commit fails rc=128
    # ("unable to auto-detect email") -- silently, per-commit, at runtime. Ask git
    # itself, with the SAME overrides the worker applies, so the check sees the
    # identity a commit would: ``git var GIT_AUTHOR_IDENT`` exits non-zero when
    # none is resolvable. The identity is not echoed; the message names the remedy.
    identity_args: list[str] = []
    if name := author_name():
        identity_args += ["-c", f"user.name={name}"]
    if email := author_email():
        identity_args += ["-c", f"user.email={email}"]
    result = subprocess.run(
        ["git", "-C", str(VAULT_PATH), *identity_args, "var", "GIT_AUTHOR_IDENT"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            "git-sync is enabled but git cannot resolve a committer identity; set "
            "VAULT_GIT_GIT_AUTHOR_NAME and VAULT_GIT_GIT_AUTHOR_EMAIL"
        )

    # Optional push heartbeat. Empty = disabled (valid). When set, it must be an
    # http(s) URL with a host, mirroring upstream validate_heartbeat (incl. the
    # port-parse so a malformed port fails closed). The URL is a capability URL
    # (secret in the path), so the messages name only the var, never the value.
    hb_url = heartbeat_url()
    if hb_url:
        try:
            parsed = urlsplit(hb_url)
            port = parsed.port  # raises ValueError on a malformed port
        except ValueError:
            raise ValueError("VAULT_GIT_HEARTBEAT_URL has a malformed port")
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            raise ValueError(
                "VAULT_GIT_HEARTBEAT_URL must be an http(s) URL with a host"
            )
        del port  # only accessed to trigger the malformed-port check
