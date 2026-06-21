"""The ``GitSyncExtension`` that loads into the upstream MCP server.

This is the empty shell every later v1 change builds on: it boots, it is gated off
by default, and when gated on with bad config it refuses to start. No change
detection, git work, worker thread, or stamping happens here -- those arrive in
later changes as new hooks on this same class.
"""

import logging

from obsidian_vault_mcp import extensions

from . import config

logger = logging.getLogger(__name__)


class GitSyncExtension(extensions.Extension):
    """In-process git-sync extension for the obsidian-web-mcp server.

    Loaded via ``serve([GitSyncExtension()])``. Reads its enable flag at construction
    so the disabled-vs-enabled decision is fixed for the process lifetime. All hooks
    are no-ops this change except ``before_indexes_start``, which runs the fail-closed
    validation backstop and logs the on/off state.
    """

    def __init__(self) -> None:
        # Snapshot the enable flag once; the rest of config is read only when enabled.
        self._enabled = config.is_enabled()

    def before_indexes_start(self, frontmatter_index) -> None:
        """Validate config (fail-closed backstop) and log whether sync is on.

        A raise here propagates out of ``serve()`` and exits the process non-zero,
        so this is the backstop to the primary check in the console entry point.
        When disabled this is a no-op beyond logging that the extension loaded but
        is off, so an operator can see it is present yet inert.
        """
        if not self._enabled:
            logger.info("git-sync extension loaded but DISABLED (VAULT_GITSYNC_ENABLED not truthy)")
            return

        config.validate_gitsync()
        logger.info("git-sync extension ENABLED")

    # register_tools, after_indexes_start, register_routes, shutdown stay no-ops this
    # change. In particular register_routes adds nothing: /health is upstream-reserved
    # and build_app() rejects any extension route on an auth-exempt path.
