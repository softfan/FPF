#!/usr/bin/env python3
"""
http_transport.py -- serve the MCP server over Streamable HTTP.

The stdio transport in ``mcp_server`` is enough for a client that can launch a
process.  An HTTP transport is for the cases it cannot: a browser-based client, a
shared instance, a container, or a client that only accepts a URL.

The protocol has a small number of requirements that are easy to get wrong, so
they are all handled in one place:

===========================  ===============================================
``POST /mcp`` + request       ``application/json`` with the response
``POST /mcp`` + notification  ``202 Accepted``, no body
``GET  /mcp``                 ``405`` -- this server starts no streams
``DELETE /mcp``               ``204`` -- the session is dropped
unknown session id            ``404``
bad ``MCP-Protocol-Version``  ``400``
bad JSON                      ``400`` with a JSON-RPC parse error
foreign ``Origin``            ``403`` -- DNS-rebinding guard
===========================  ===============================================

Sessions are stateful only in the sense the protocol requires: ``initialize``
mints an id, later requests must carry it.  No session state is stored beyond
the id, so a restart simply invalidates the ids -- which the protocol already
tells a client how to handle (start a new session).
"""

from __future__ import annotations

import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from skillmaker.mcp_server import SUPPORTED_VERSIONS, decode_message, message_kind

#: Loopback names an ``Origin`` header may carry.  Anything else is refused:
#: without this check a web page could drive a local server through the browser.
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}

MCP_PATH = "/mcp"


class SessionStore:
    """Session ids and nothing else."""

    def __init__(self) -> None:
        self._ids: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _expire(self) -> None:
        now = time.monotonic()
        self._ids = {key: expires for key, expires in self._ids.items() if expires > now}

    def create(self) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._expire()
            if len(self._ids) >= 1024:
                raise ValueError("session limit reached; close a session or wait for expiry")
            self._ids[token] = time.monotonic() + 3600
        return token

    def valid(self, token: Optional[str]) -> bool:
        with self._lock:
            self._expire()
            return bool(token) and token in self._ids

    def drop(self, token: Optional[str]) -> bool:
        with self._lock:
            self._expire()
            return self._ids.pop(token, None) is not None

    def __len__(self) -> int:
        with self._lock:
            self._expire()
            return len(self._ids)


def _origin_allowed(origin: str) -> bool:
    """A browser origin must be loopback; a missing Origin is allowed.

    Non-browser clients (curl, an SDK, another server) send no ``Origin`` at
    all.  Requiring one would break them; accepting a foreign one would expose
    the server to a page the user happens to have open.
    """
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
        # Origin is an origin, not an arbitrary URL with a trusted hostname.
        parsed.port  # force validation of malformed/non-numeric ports
        return (parsed.scheme in ("http", "https") and parsed.hostname in LOOPBACK_HOSTS
                and parsed.username is None and parsed.password is None
                and not parsed.path and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    """One request.  ``server`` carries the MCP server and the session store."""

    protocol_version = "HTTP/1.1"
    server_version = "fpf-skills-mcp/1.0"

    # --- plumbing ---------------------------------------------------------
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, fmt: str, *args) -> None:  # noqa: D102
        if self.server.verbose:                       # type: ignore[attr-defined]
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: Optional[bytes] = None,
              content_type: str = "application/json",
              headers: Optional[Dict[str, str]] = None) -> None:
        self.send_response(code)
        if self.close_connection:
            self.send_header("Connection", "close")
        if code == 405:
            self.send_header("Allow", "POST, DELETE")
        if body is not None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
        else:
            self.send_header("Content-Length", "0")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, code: int, payload: object,
              headers: Optional[Dict[str, str]] = None) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self._send(code, body, "application/json", headers)

    def _error(self, code: int, message: str,
               rpc_code: Optional[int] = None) -> None:
        # Rejected POST bodies may remain unread; never interpret them as the
        # next request on this connection.
        self.close_connection = True
        if rpc_code is None:
            self._json(code, {"error": message})
            return
        self._json(code, {"jsonrpc": "2.0", "id": None,
                          "error": {"code": rpc_code, "message": message}})

    # --- guards -----------------------------------------------------------
    def _guard_origin(self) -> bool:
        if len(self.headers.get_all("Origin", [])) <= 1 and _origin_allowed(self.headers.get("Origin", "")):
            return True
        self._error(403, "origin not allowed: this server accepts loopback "
                         "origins only")
        return False

    def _guard_version(self) -> bool:
        if (len(self.headers.get_all("MCP-Protocol-Version", [])) > 1
                or len(self.headers.get_all("Mcp-Session-Id", [])) > 1):
            self._error(400, "duplicate protocol/session headers are not supported")
            return False
        version = self.headers.get("MCP-Protocol-Version", "")
        if not version or version in SUPPORTED_VERSIONS:
            return True
        self._error(400, f"unsupported MCP-Protocol-Version {version!r}; "
                         f"supported: {', '.join(SUPPORTED_VERSIONS)}")
        return False

    def _session(self) -> Optional[str]:
        return self.headers.get("Mcp-Session-Id") or None

    def _guard_empty_body(self) -> bool:
        """GET/DELETE bodies are unsupported; do not leave bytes on keepalive."""
        lengths = self.headers.get_all("Content-Length", [])
        if (self.headers.get("Transfer-Encoding") or len(lengths) > 1
                or (lengths and lengths[0] != "0")):
            self._error(400, "this method does not accept a request body")
            return False
        return True

    # --- verbs ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if not self._guard_origin() or not self._guard_version() or not self._guard_empty_body():
            return
        path = urlparse(self.path).path
        if path in ("/", "/connect", "/connect.md"):
            page = self.server.connect_page()          # type: ignore[attr-defined]
            self._send(200, page.encode("utf-8"), "text/markdown; charset=utf-8")
            return
        if path == "/health":
            self._json(200, {
                "status": "ok",
                "protocol": SUPPORTED_VERSIONS[0],
                "sessions": len(self.server.sessions),  # type: ignore[attr-defined]
                "corpus": self.server.mcp.call("get_corpus_status", {}),  # type: ignore[attr-defined]
            })
            return
        if path == MCP_PATH:
            # No server-initiated streams.  The specification requires 405 here
            # rather than an empty 200, so a client can tell the difference
            # between "nothing to say" and "this server does not do that".
            self._error(405, "this server does not open server-to-client "
                             "streams; use POST")
            return
        self._error(404, f"no such path: {path}")

    def do_POST(self) -> None:  # noqa: N802
        if not self._guard_origin() or not self._guard_version():
            return
        if urlparse(self.path).path != MCP_PATH:
            self._error(404, "the MCP endpoint is " + MCP_PATH)
            return

        # A malformed Content-Length is a client error, not a server crash:
        # reading with a bad length would raise out of the handler and drop the
        # connection without a status line.
        if self.headers.get("Transfer-Encoding"):
            self._error(400, "Transfer-Encoding is not supported")
            return
        if len(self.headers.get_all("Content-Length", [])) > 1:
            self._error(400, "duplicate Content-Length is not supported")
            return
        try:
            value = self.headers.get("Content-Length", "0")
            if not value.isascii() or not value.isdecimal():
                raise ValueError("invalid length")
            length = int(value)
        except ValueError:
            self._error(400, "Content-Length must be an integer", rpc_code=-32700)
            return
        if length > 1024 * 1024:
            self._error(413, "request body exceeds the 1 MiB limit")
            return
        try:
            raw = self.rfile.read(length) if length else b""
        except TimeoutError:
            self._error(408, "request body read timed out")
            return
        try:
            message = decode_message(raw.decode("utf-8"))
        except (ValueError, RecursionError) as exc:
            self._error(400, f"parse error: {exc}", rpc_code=-32700)
            return
        try:
            kind = message_kind(message)
        except ValueError as exc:
            self._error(400, str(exc), rpc_code=-32600)
            return

        method = message.get("method")

        # Initialization is the only request that may arrive without a session.
        if method == "initialize":
            response = self.server.mcp.handle(message)  # type: ignore[attr-defined]
            if not response or "error" in response:
                self._json(400, response or {"error": "initialize requires an id"})
                return
            try:
                session = self.server.sessions.create()  # type: ignore[attr-defined]
            except ValueError as exc:
                self._error(503, str(exc))
                return
            self._json(200, response, {"Mcp-Session-Id": session})
            return

        session = self._session()
        if not self.server.sessions.valid(session):     # type: ignore[attr-defined]
            self._error(404, "unknown or expired session; send initialize again")
            return

        if kind != "request":
            # A notification is accepted, not answered.
            self.server.mcp.handle(message)             # type: ignore[attr-defined]
            self._send(202)
            return

        response = self.server.mcp.handle(message)      # type: ignore[attr-defined]
        self._json(200, response, {"Mcp-Session-Id": session})

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._guard_origin() or not self._guard_version() or not self._guard_empty_body():
            return
        if urlparse(self.path).path != MCP_PATH:
            self._error(404, "the MCP endpoint is " + MCP_PATH)
            return
        session = self._session()
        if not self.server.sessions.valid(session):     # type: ignore[attr-defined]
            self._error(404, "unknown or expired session")
            return
        self.server.sessions.drop(session)              # type: ignore[attr-defined]
        self._send(204)


class HttpServer(ThreadingHTTPServer):
    """Threading server carrying the MCP server, its sessions and a page."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: Tuple[str, int], mcp, connect_page,
                 verbose: bool = False, allow_maker_tools: bool = False):
        self.mcp = mcp
        self.mcp.allow_maker_tools = allow_maker_tools
        self._connections = threading.BoundedSemaphore(32)
        self.sessions = SessionStore()
        self.connect_page = connect_page
        self.verbose = verbose
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self._connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connections.release()


def serve(mcp, host: str = "127.0.0.1", port: int = 8765,
          connect_page=None, verbose: bool = False,
          allow_maker_tools: bool = False) -> int:
    """Run until interrupted.  Binds to loopback unless told otherwise."""
    page = connect_page or (lambda: "# MCP endpoint\n\nPOST /mcp\n")
    httpd = HttpServer((host, port), mcp, page, verbose, allow_maker_tools)
    scheme_host = f"http://{host}:{httpd.server_port}"
    print(f"listening on {scheme_host}{MCP_PATH}", file=sys.stderr)
    print(f"  connect page: {scheme_host}/", file=sys.stderr)
    print(f"  health:       {scheme_host}/health", file=sys.stderr)
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("  warning: bound to a non-loopback address; anyone who can "
              "reach this port can read the corpus", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopping", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0
