"""Loading operator-declared extensions alongside the git-sync extension.

Upstream's extension seam gives every extension its own console entry point
calling ``serve([YourExtension()])`` and no way to compose two, so composition is
this package's entry point's job. ``VAULT_MCP_EXTENSIONS`` names the additional
extensions to load; this module owns that whole concern -- the env read, spec
splitting, resolution, and instantiation -- leaving ``main.py`` to append the
result after ``GitSyncExtension``.

Deliberately self-contained, and deliberately NOT in ``config.py``: that module
holds git-sync settings (``VAULT_GIT_*``) and does parsing -- raw string in,
typed value out. This does resolution, importing operator-named third-party
modules and running their import side effects, and it configures the server host
rather than git sync. The variable also sits in the upstream ``VAULT_MCP_*``
namespace, defined by this package only until upstream defines it: if upstream
ever ships extension composition itself, this module is deleted whole rather
than unpicked from the git-sync config.

TRUST MODEL: a declared extension is FULLY-TRUSTED, in-process code running with
the server's full privileges -- it can read the bearer token and OAuth secrets
from the environment, read/write the vault, and mutate any route. This is not a
sandbox. Loading is therefore EXPLICIT OPT-IN: only what the operator names is
loaded. There is deliberately no entry-point-group or filesystem discovery,
because installing a package is not consent to run it with those privileges.
"""

import importlib
import os

# Additional extensions to load, as a comma-separated list of
# ``module.path:ClassName`` import specs. EMPTY/unset = none, and then no import
# machinery runs at all.
#
# Kept raw and resolved in load_extra_extensions() so a typo fails CLOSED at
# startup rather than at import or, worse, boots a server missing the extension
# an operator asked for.
#
#   VAULT_MCP_EXTENSIONS -- "pkg.mod:Class,other.mod:Class", or "" for none.
VAULT_MCP_EXTENSIONS = os.environ.get("VAULT_MCP_EXTENSIONS", "")


def _resolve_extension(spec: str):
    """Resolve one ``module.path:ClassName`` spec to an ``Extension`` subclass.

    Raises ``ValueError`` naming the offending spec for every rejection -- a
    malformed spec, an unimportable module, a missing attribute, or a target that
    is not an ``extensions.Extension`` subclass. Never returns a partial result:
    the caller either gets a usable class or an error identifying what was wrong.
    """
    # Imported lazily to keep this module importable without the upstream server.
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


def load_extra_extensions() -> list:
    """Return one instance per operator-declared extension, in declaration order.

    Each resolved class is constructed with NO arguments -- an extension takes its
    own configuration from its own environment, as every extension in this
    ecosystem does. A repeated declaration yields two instances rather than being
    silently de-duplicated: a duplicate entry is more likely a config mistake
    worth leaving visible than an intent to load twice.

    This IS the startup validation for ``VAULT_MCP_EXTENSIONS``: resolution
    produces the instances the entry point needs and raises ``ValueError`` on any
    bad entry, so there is no separate ``validate_*`` pass to run (one would
    either re-import every declared module or discard its own result).

    Empty when nothing is declared -- an unset, empty, whitespace-only, or
    comma-only value imports nothing at all. Padding and a trailing or repeated
    comma from a hand-edited env file are tolerated rather than rejected.

    Resolution is ALL-OR-NOTHING: one bad entry raises and nothing is returned,
    because a server running without the extension an operator asked for is a
    silently wrong deployment.

    Independent of git sync being enabled -- a declared extension must load
    whether or not git sync itself is turned on.
    """
    return [
        _resolve_extension(spec)()
        for spec in (raw.strip() for raw in VAULT_MCP_EXTENSIONS.split(","))
        if spec
    ]
