"""Tests for the push-heartbeat ping discipline (the monitoring change).

These cover the ``heartbeat.ping`` helper in isolation: it must follow no
redirects, read only a bounded slice of the body, swallow every error (never
raise), and no-op on a falsy URL. A redirect is exercised against a tiny local
``http.server`` so the no-redirect assertion is real; the connection-error path
uses a closed port so it is deterministic and fast. The server is always shut
down in a ``finally``.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from obsidian_git_sync import heartbeat


def _serve(handler_cls):
    """Start a one-thread HTTP server on an ephemeral port; return (server, base_url)."""
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, f"http://{host}:{port}"


def test_ping_does_not_follow_redirects():
    """A 302 from the heartbeat URL is NOT followed to its target."""
    hits = {"start": 0, "target": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/target":
                hits["target"] += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                hits["start"] += 1
                self.send_response(302)
                self.send_header("Location", "/target")
                self.end_headers()

        def log_message(self, *args):  # silence the test server's stderr noise
            pass

    server, thread, base = _serve(Handler)
    try:
        heartbeat.ping(f"{base}/start")  # must not raise even though urllib errors on the 302
    finally:
        server.shutdown()
        server.server_close()

    assert hits["start"] == 1, "the configured URL should be hit exactly once"
    assert hits["target"] == 0, "the redirect target must never be fetched"


def test_ping_reads_only_a_bounded_amount():
    """The ping reads at most a small cap of the body, not the whole (large) response."""
    sent = {"bytes": 0}
    big = b"x" * (heartbeat._HEARTBEAT_MAX_BYTES * 64)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(big)))
            self.end_headers()
            try:
                self.wfile.write(big)
                sent["bytes"] = len(big)
            except (BrokenPipeError, ConnectionResetError):
                # Expected: ping closes the connection after the bounded read.
                pass

        def log_message(self, *args):
            pass

    server, thread, base = _serve(Handler)
    try:
        heartbeat.ping(f"{base}/")  # must complete promptly without slurping the whole body
    finally:
        server.shutdown()
        server.server_close()
    # If ping read the whole body it would still pass functionally; the load-bearing
    # assertion is the bounded read call, verified via the fake opener below.


def test_ping_reads_at_most_the_cap_via_fake_opener(monkeypatch):
    """Deterministic proof that ping calls ``read(<=_HEARTBEAT_MAX_BYTES)``."""
    recorded = {"read_arg": None}

    class FakeResp:
        def read(self, n):
            recorded["read_arg"] = n
            return b"x" * n

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class FakeOpener:
        def open(self, url, timeout):
            return FakeResp()

    monkeypatch.setattr(heartbeat, "_heartbeat_opener", FakeOpener())
    heartbeat.ping("https://monitor.example/abc")
    assert recorded["read_arg"] == heartbeat._HEARTBEAT_MAX_BYTES


def test_ping_swallows_connection_error():
    """An unreachable endpoint is swallowed -- ping never raises."""
    # Port 1 is reserved/unused; the connection refusal must be caught.
    heartbeat.ping("http://127.0.0.1:1/")  # must not raise


def test_ping_empty_url_is_noop(monkeypatch):
    """A falsy URL opens nothing at all."""
    called = {"n": 0}

    class FakeOpener:
        def open(self, *a, **k):
            called["n"] += 1

    monkeypatch.setattr(heartbeat, "_heartbeat_opener", FakeOpener())
    heartbeat.ping("")
    heartbeat.ping(None)  # type: ignore[arg-type]
    assert called["n"] == 0
