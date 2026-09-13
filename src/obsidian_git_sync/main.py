"""Console entry point: our own ``serve`` wrapper, not the stock ``vault-mcp``.

The stock entry point runs ``serve()`` with no extensions. We construct a
``GitSyncExtension``, run ``validate_gitsync()`` here -- with the same
``ValueError -> log -> sys.exit(1)`` handling upstream uses for ``validate_config()``
-- then hand off to ``serve([ext])``. Validating in the entry point yields a clean
fail-closed message instead of a raw traceback out of ``before_indexes_start``
(which still backstops it).

It is also the process's assembly point, so it is where extension COMPOSITION
happens: an operator naming additional extensions in ``VAULT_MCP_EXTENSIONS``
gets them appended after ``GitSyncExtension`` in the single ``serve()`` call
here. The loading itself lives in ``extension_hosting``; this module only
decides the order and runs the load inside the same fail-closed block as the
git-sync validation, so a bad declaration refuses the boot rather than raising
mid-startup.
"""

import logging
import sys

from obsidian_vault_mcp.server import serve

from . import config
from .extension import GitSyncExtension
from .extension_hosting import load_extra_extensions

logger = logging.getLogger(__name__)


def main() -> None:
    """Build the extension list, validate fail-closed, then run the upstream server."""
    ext = GitSyncExtension()

    # One fail-closed block over every startup check: each ValueError already
    # names its own offending variable, so a shared prefix loses nothing and the
    # next validated concern joins by adding a line rather than another block.
    # load_extra_extensions() is called separately from validate_gitsync()
    # because that one returns early when git sync is disabled, and a declared
    # extension must load either way.
    try:
        config.validate_gitsync()
        extras = load_extra_extensions()
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        sys.exit(1)

    if extras:
        logger.info(
            "Loading additional extensions from VAULT_MCP_EXTENSIONS: %s",
            ", ".join(f"{type(x).__module__}:{type(x).__qualname__}" for x in extras),
        )

    # GitSyncExtension stays FIRST so its hook runs before any declared
    # extension's at each upstream lifecycle stage; declared extensions follow in
    # declaration order, the only ordering an operator can reason about.
    serve([ext, *extras])


if __name__ == "__main__":
    main()
