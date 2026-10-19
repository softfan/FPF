#!/usr/bin/env python3
"""Optional Bash/curl startup regressions; run after building skills/.

Not part of the dependency-free Python suites: requires Bash and curl, like the
HTTP walkthrough it exercises. Slow-start coverage deliberately adds six seconds.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from unittest.mock import Mock, patch

from test_mcp_http import wait_ready, stop_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skill-maker/src"))
from skillmaker._fpf_common import ensure_utf8_stdio

ensure_utf8_stdio()


def main():
    if not shutil.which("bash") or not shutil.which("curl"):
        print("SKIP: startup regressions require Bash and curl")
        return 0
    if not (ROOT / "skills/index.json").is_file():
        print("Build skills/ first", file=sys.stderr)
        return 1
    passed = failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS {name}")
        else:
            failed += 1
            print(f"  FAIL {name}")

    preferred = Path("/tmp/opencode")
    with tempfile.TemporaryDirectory(prefix="http startup ",
                                     dir=preferred if preferred.is_dir() else None) as tmp:
        wrapper = Path(tmp) / "python shim"
        wrapper.write_bytes(b'''#!/usr/bin/env bash
if [ "${1:-}" = "-u" ]; then
    case "$STARTUP_PROBE" in
        slow) sleep 6 ;;
        crash) echo 'startup-probe-crash' >&2; exit 23 ;;
        timeout) exec "$REAL_PYTHON" -c 'import time; time.sleep(30)' ;;
    esac
fi
if [ "$STARTUP_PROBE" = "crlf" ] && [ "${1:-}" = "-c" ]; then
    exec "$REAL_PYTHON" -c 'import sys; sys.stdout.reconfigure(newline="\\r\\n"); code=sys.argv[1]; sys.argv=sys.argv[1:]; exec(compile(code,"<string>","exec"))' "$2" "${@:3}"
fi
exec "$REAL_PYTHON" "$@"
''')
        wrapper.chmod(0o755)
        log = Path(tmp) / "native-server.log"
        log.write_bytes(b"")
        child = Mock()
        child.poll.return_value = 23
        try:
            wait_ready(child, log, 5)
        except RuntimeError as exc:
            check("native readiness reports child crash", "code 23" in str(exc))
        else:
            check("native readiness reports child crash", False)
        child.poll.return_value = None
        with patch("test_mcp_http.time.monotonic", side_effect=[0, 2]):
            try:
                wait_ready(child, log, 1)
            except RuntimeError as exc:
                check("native readiness has a bounded timeout", "timeout" in str(exc))
            else:
                check("native readiness has a bounded timeout", False)
        stop_server(child)
        check("native cleanup terminates and waits for child",
              child.terminate.call_count == 1 and child.wait.call_count == 1)
        child.reset_mock()
        child.wait.side_effect = [subprocess.TimeoutExpired("probe", 5), 0]
        stop_server(child)
        check("native cleanup escalates to kill after timeout", child.kill.call_count == 1)
        result = subprocess.run([sys.executable, "-B", "skill-maker/tests/test_mcp_http.py"],
            cwd=ROOT, env={**os.environ, "PATH": "", "PYTHON": "must-not-be-used",
                           "http_proxy": "http://127.0.0.1:1", "ALL_PROXY": "http://127.0.0.1:1"},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", timeout=80)
        check("native walkthrough needs no PATH/Bash/curl and ignores PYTHON/proxy overrides",
              result.returncode == 0 and "Results: 29 passed, 0 failed" in result.stdout)
        if result.returncode:
            print(result.stdout)
        for mode, timeout in (("slow", "30"), ("crlf", "30"), ("crash", "5"), ("timeout", "1"), ("invalid", "bad")):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env = {**os.environ, "PYTHON": str(wrapper), "REAL_PYTHON": sys.executable,
                   "STARTUP_PROBE": mode, "MCP_STARTUP_TIMEOUT": timeout,
                   "MCP_HOST": "127.0.0.1", "MCP_PORT": str(port), "START_SERVER": "1",
                   "MCP_ENDPOINT": f"http://127.0.0.1:{port}/mcp", "MCP_TOKEN": ""}
            if mode == "slow":
                # The locally spawned child must bypass even a broken proxy.
                env.update(http_proxy="http://127.0.0.1:1", ALL_PROXY="http://127.0.0.1:1",
                           no_proxy="", NO_PROXY="")
            result = subprocess.run(["bash", "skill-maker/tests/test-mcp-http.sh"],
                                    cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", timeout=50)
            output = result.stdout
            if mode == "slow":
                check("slow startup beyond old five-second window completes all HTTP tests",
                      result.returncode == 0 and "Results: 29 passed, 0 failed" in output)
            elif mode == "crlf":
                check("Windows-style Python stdout completes all HTTP tests",
                      result.returncode == 0 and "Results: 29 passed, 0 failed" in output)
            elif mode == "crash":
                check("startup crash reports original exit code and stderr",
                      result.returncode != 0 and "Server exited with code 23" in output
                      and "startup-probe-crash" in output)
            elif mode == "timeout":
                check("readiness timeout reports health probe error",
                      result.returncode != 0 and "limit 1s" in output
                      and "Last health probe error:" in output and "curl:" in output)
            else:
                check("invalid startup timeout fails before starting server",
                      result.returncode != 0 and "must be an integer" in output)
            if result.returncode != 0:
                check(f"{mode}: diagnostic directory is retained", "diagnostics retained in:" in output)
            if mode in ("slow", "crlf") and result.returncode != 0:
                print(output)
        result = subprocess.run(["bash", "skill-maker/tests/test-mcp-http.sh"], cwd=ROOT,
            env={**os.environ, "PYTHON": str(Path(tmp) / "missing python")},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", timeout=10)
        check("shell never replaces an explicitly selected missing interpreter",
              result.returncode != 0 and "no fallback was attempted" in result.stdout
              and "Starting server" not in result.stdout)
    print(f"Results: {passed} passed, {failed} failed / {passed + failed} total")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
