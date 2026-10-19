#!/usr/bin/env python3
"""Native subprocess HTTP walkthrough: no Bash, curl, WSL or third-party packages.

Build skills/ first. The child uses sys.executable, binds an ephemeral loopback
port and reports its actual address on stderr. Mirrors the shell's 29 checks.
"""
from __future__ import annotations

import argparse
import http.client
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skill-maker/src"))
from skillmaker._fpf_common import ensure_utf8_stdio

ensure_utf8_stdio()
SERVER = ROOT / "skill-maker/src/skillmaker/mcp_server.py"


def wait_ready(process, log_path, timeout):
    """Wait for this child's address, not an unrelated service on a fixed port."""
    deadline = time.monotonic() + timeout
    last_error = "child has not reported a listening address"
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise RuntimeError(f"server exited with code {code}")
        log = log_path.read_text(encoding="utf-8", errors="replace")
        address = re.search(r"listening on http://127\.0\.0\.1:(\d+)/mcp", log)
        if address:
            port = int(address.group(1))
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            try:
                connection.request("GET", "/health")
                response = connection.getresponse()
                body = json.loads(response.read())
                if response.status == 200 and body.get("status") == "ok":
                    return port
                last_error = f"health returned {response.status}: {body!r}"
            except (OSError, ValueError, http.client.HTTPException) as exc:
                last_error = str(exc)
            finally:
                connection.close()
        time.sleep(0.1)
    raise RuntimeError(f"readiness timeout after {timeout}s: {last_error}")


def stop_server(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def walkthrough(port, check):
    def request(method, path="/mcp", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict((k.lower(), v) for k, v in response.getheaders()), response.read()
        finally:
            connection.close()

    def post(message, session="", headers=None):
        fields = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if session:
            fields["Mcp-Session-Id"] = session
        fields.update(headers or {})
        return request("POST", body=json.dumps(message).encode("utf-8"), headers=fields)

    def call(name, arguments, request_id):
        _, _, body = post({"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}}, session)
        return json.loads(body)["result"]

    _, _, body = request("GET", "/health")
    health = json.loads(body)
    check("GET /health returns status ok", health.get("status") == "ok")
    check("health reports a corpus", health.get("corpus", {}).get("patterns", 0) > 0)

    _, headers, body = post({"jsonrpc": "2.0", "method": "initialize", "id": 1,
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "native-http-test", "version": "1.0.0"}}})
    session = headers.get("mcp-session-id", "")
    check("Mcp-Session-Id received", bool(session))
    if not session:
        raise RuntimeError(f"cannot continue without a session: {body!r}")
    result = json.loads(body).get("result", {})
    check("protocol version negotiated", result.get("protocolVersion") == "2025-06-18")
    check("serverInfo.name present", bool(result.get("serverInfo", {}).get("name")))

    status, _, _ = post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    check("notification accepted with 202", status == 202)
    _, _, body = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)
    tools = json.loads(body)["result"]["tools"]
    check("at least ten tools listed", len(tools) >= 10)
    names = {tool["name"] for tool in tools}
    for name in ("search", "read_pattern", "read_section", "get_table_of_contents",
                 "list_publications", "get_corpus_status", "backlinks", "route", "entries", "glossary"):
        check(f"tool {name} present", name in names)

    result = call("get_corpus_status", {}, 3)
    check("get_corpus_status returned a result", result.get("isError") is False)
    result = call("search", {"q": "decision", "limit": 3}, 4)
    check("search returned units", "pattern_id" in json.dumps(result))
    result = call("read_pattern", {"pattern_id": "PSDA.1", "tier": "contract"}, 5)
    text = json.loads(result["content"][0]["text"])
    check("read_pattern tier=contract returned bytes", text.get("returned_bytes", 0) > 0)
    result = call("read_pattern", {"pattern_id": "NOPE.99"}, 6)
    check("unknown unit is reported as an error", result.get("isError") is True)

    message = {"jsonrpc": "2.0", "id": 7, "method": "tools/list"}
    status, _, _ = post(message, "not-a-real-session")
    check("unknown session -> 404", status == 404)
    status, _, _ = post(message, session, {"MCP-Protocol-Version": "1999-01-01"})
    check("bad MCP-Protocol-Version -> 400", status == 400)
    status, _, _ = post(message, session, {"Origin": "https://example.com"})
    check("foreign Origin -> 403", status == 403)
    status, _, _ = request("POST", body=b"this is not json", headers={
        "Content-Type": "application/json", "Mcp-Session-Id": session})
    check("malformed JSON -> 400", status == 400)
    status, _, _ = request("GET")
    check("GET /mcp -> 405 (no server streams)", status == 405)
    status, _, _ = request("DELETE", headers={"Mcp-Session-Id": session})
    check("DELETE -> 204", status == 204)
    status, _, _ = post(message, session)
    check("session is gone after DELETE", status == 404)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-timeout", type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.startup_timeout <= 3600:
        parser.error("--startup-timeout must be from 1 to 3600 seconds")
    if sys.version_info < (3, 9):
        print(f"Python 3.9+ required; running {sys.version.split()[0]} at {sys.executable}", file=sys.stderr)
        return 1
    passed = failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
        else:
            failed += 1
        print(f"  {'ok' if condition else 'FAIL'} {name}")

    preferred = Path("/tmp/opencode")
    work = Path(tempfile.mkdtemp(prefix="fpf-native-http-", dir=preferred if preferred.is_dir() else None))
    log = work / "server.log"
    child = None
    success = False
    print(f"HTTP walkthrough Python: {sys.executable} ({sys.version.split()[0]})")
    try:
        with log.open("wb") as stream:
            child = subprocess.Popen([sys.executable, "-u", str(SERVER), "--http", "127.0.0.1:0"],
                                     cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            port = wait_ready(child, log, args.startup_timeout)
            check(f"server started on 127.0.0.1:{port}", True)
            walkthrough(port, check)
        success = failed == 0
    except (OSError, ValueError, KeyError, IndexError, RuntimeError, http.client.HTTPException) as exc:
        check(str(exc), False)
    finally:
        if child is not None:
            stop_server(child)
        if success:
            log.unlink()
            work.rmdir()
        else:
            print("Server log (last 30 lines):", file=sys.stderr)
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]), file=sys.stderr)
            print(f"Diagnostics retained in: {work}", file=sys.stderr)
    print(f"Results: {passed} passed, {failed} failed")
    return int(not success)


if __name__ == "__main__":
    raise SystemExit(main())
