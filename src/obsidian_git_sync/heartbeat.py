"""Push-heartbeat ping helper, porting the upstream ping discipline.

The worker fires ``ping(url)`` after a successful push so a push-style monitor
(Uptime Kuma, Healthchecks.io, Cronitor, …) sees that git sync reached the
remote. The discipline is ported (not imported) from upstream's private
``server._heartbeat_ping`` / ``_NoRedirect``:

- follow NO redirects -- a typo'd/compromised monitor must not bounce the ping
  to an arbitrary target (or scheme);
- read at most a small cap of the body -- a liveness GET does not need it, and a
  hostile/large body must not be pulled into memory;
- a short timeout, so a hanging endpoint cannot wedge the single worker thread;
- log only the host + exception type on failure -- the URL is a capability URL
  (the secret is in the path), so it (and the exception string) must never be
  logged;
- never raise -- a flaky monitor must never affect sync.
"""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# Liveness pings don't need the response body; read just enough to complete the
# request without pulling a large/hostile body into memory.
_HEARTBEAT_MAX_BYTES = 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to follow redirects on the heartbeat GET.

    The configured URL is operator-trusted, but a redirect is not -- following one
    would let a compromised/typo'd monitor bounce the ping to an arbitrary target
    (incl. another scheme). Returning None makes urllib raise instead of follow.
    """

    def redirect_request(self, *args, **kwargs):
        return None


_heartbeat_opener = urllib.request.build_opener(_NoRedirect)


def ping(url: str) -> None:
    """Send a single liveness GET to ``url``; fail-soft (never raises).

    A no-op when ``url`` is falsy. Does not follow redirects, reads at most
    ``_HEARTBEAT_MAX_BYTES`` of the body with a short timeout, and on any failure
    logs only the host + exception type (never the URL, which may carry a secret).
    """
    if not url:
        return
    # Resolve the host up front so the failure log never needs the raw URL.
    host = urllib.parse.urlsplit(url).hostname or "?"
    try:
        with _heartbeat_opener.open(url, timeout=10) as resp:
            resp.read(_HEARTBEAT_MAX_BYTES)
    except Exception as e:
        logger.warning("Push heartbeat to %s failed: %s", host, type(e).__name__)
