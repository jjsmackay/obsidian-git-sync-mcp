"""Console entry point: our own ``serve`` wrapper, not the stock ``vault-mcp``.

The stock entry point runs ``serve()`` with no extensions. We construct a
``GitSyncExtension``, run ``validate_gitsync()`` here -- with the same
``ValueError -> log -> sys.exit(1)`` handling upstream uses for ``validate_config()``
-- then hand off to ``serve([ext])``. Validating in the entry point yields a clean
fail-closed message instead of a raw traceback out of ``before_indexes_start``
(which still backstops it).
"""

import logging
import sys

from obsidian_vault_mcp.server import serve

from . import config
from .extension import GitSyncExtension

logger = logging.getLogger(__name__)


def main() -> None:
    """Build the extension, validate fail-closed, then run the upstream server."""
    ext = GitSyncExtension()

    try:
        config.validate_gitsync()
    except ValueError as e:
        logger.error(f"Invalid git-sync configuration: {e}")
        sys.exit(1)

    serve([ext])


if __name__ == "__main__":
    main()
