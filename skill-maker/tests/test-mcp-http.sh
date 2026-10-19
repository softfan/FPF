#!/usr/bin/env bash
# test-mcp-http.sh -- end-to-end check of the Streamable HTTP transport.
#
# Runs the server, walks the protocol by hand with curl, and asserts each step.
# Nothing here needs a client library: the point is to prove the endpoint works
# from a shell, which is the hardest case to fake.
#
# Usage:
#   bash skill-maker/tests/test-mcp-http.sh        # start, test, stop
#   MCP_ENDPOINT=http://127.0.0.1:8765/mcp bash skill-maker/tests/test-mcp-http.sh
#   MCP_TOKEN=... bash skill-maker/tests/test-mcp-http.sh   # when auth is required
#   MCP_STARTUP_TIMEOUT=120 bash skill-maker/tests/test-mcp-http.sh # slower disks
#
# Exit code: 0 when every assertion passes.

set -u

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-8765}"
MCP_ENDPOINT="${MCP_ENDPOINT:-http://$HOST:$PORT/mcp}"
MCP_TOKEN="${MCP_TOKEN:-}"
START_SERVER="${START_SERVER:-1}"
STARTUP_TIMEOUT="${MCP_STARTUP_TIMEOUT:-60}"
HEALTH_ENDPOINT="${MCP_ENDPOINT%/mcp}/health"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # skill-maker/tests
MAKER_DIR="$(dirname "$SCRIPT_DIR")"                          # skill-maker
REPO_ROOT="$(dirname "$MAKER_DIR")"                           # repository root
PKG_DIR="$MAKER_DIR/src/skillmaker"                           # the package
if [ -z "${PYTHON:-}" ]; then
    PYTHON=python3
    if ! command -v "$PYTHON" >/dev/null 2>&1 && command -v python >/dev/null 2>&1; then
        PYTHON=python
    fi
fi
# Never replace an explicitly selected interpreter (especially across WSL).
if ! "$PYTHON" -c 'import sys; print("HTTP walkthrough Python: %s (%s)" % (sys.executable, sys.version.split()[0])); sys.exit(0 if sys.version_info >= (3, 9) else "Python 3.9+ required; select PYTHON explicitly")'; then
    echo 'Cannot run HTTP walkthrough with the selected PYTHON; no fallback was attempted.' >&2
    exit 1
fi

PASSED=0
FAILED=0
SERVER_PID=""
TMP_BASE="${TMPDIR:-/tmp}"
[ -d /tmp/opencode ] && TMP_BASE=/tmp/opencode
WORK_DIR=$(mktemp -d "$TMP_BASE/fpf-mcp-http.XXXXXX") || exit 1

# A failed endpoint must not hang the complete build indefinitely.
curl() {
    # A local child must not be reached through a corporate/system proxy.
    local args=()
    [ "$START_SERVER" = "1" ] && args+=(--noproxy "$HOST")
    command curl --connect-timeout 3 --max-time 15 "${args[@]}" "$@"
}

pass() { PASSED=$((PASSED + 1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { FAILED=$((FAILED + 1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; [ -n "${2:-}" ] && printf '       %s\n' "$2"; }
step() { printf '\n%s\n' "$1"; }

cleanup() {
    local status=$?
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null
        wait "$SERVER_PID" 2>/dev/null
    fi
    if [ "$status" -ne 0 ]; then
        printf 'HTTP test failed; diagnostics retained in: %s\n' "$WORK_DIR" >&2
    else
        rm -f "$WORK_DIR/body" "$WORK_DIR/headers" "$WORK_DIR/server.log" \
            "$WORK_DIR/readiness.log" "$WORK_DIR/discard"
        rmdir "$WORK_DIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT

auth_header() {
    if [ -n "$MCP_TOKEN" ]; then printf 'Authorization: Bearer %s' "$MCP_TOKEN"; fi
}

# post BODY -> prints response body (callers use command substitution).
post() {
    local body="$1" session="${2:-}"
    local args=(-sS -o "$WORK_DIR/body" -X POST
        -H 'Content-Type: application/json'
        -H 'Accept: application/json, text/event-stream')
    [ -n "$MCP_TOKEN" ] && args+=(-H "$(auth_header)")
    [ -n "$session" ] && args+=(-H "Mcp-Session-Id: $session")
    curl "${args[@]}" -d "$body" "$MCP_ENDPOINT" 2>/dev/null
    cat "$WORK_DIR/body" 2>/dev/null
    rm -f "$WORK_DIR/body"
}

json_get() { printf '%s' "$1" | "$PYTHON" -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: raise SystemExit
for k in sys.argv[1].split('.'):
    if isinstance(d,list): d=d[int(k)]
    elif isinstance(d,dict): d=d.get(k)
    else: d=None
    if d is None: break
print('' if d is None else d, end='')
" "$2" 2>/dev/null; }

# ---------------------------------------------------------------------------
# Start the server when we are testing a local build.
# ---------------------------------------------------------------------------
if [ "$START_SERVER" = "1" ]; then
    case "$STARTUP_TIMEOUT" in
        ''|*[!0-9]*) echo 'MCP_STARTUP_TIMEOUT must be an integer from 1 to 3600' >&2; exit 1 ;;
    esac
    if [ "${#STARTUP_TIMEOUT}" -gt 4 ] || [ "$STARTUP_TIMEOUT" -lt 1 ] || [ "$STARTUP_TIMEOUT" -gt 3600 ]; then
        echo 'MCP_STARTUP_TIMEOUT must be an integer from 1 to 3600' >&2
        exit 1
    fi
    STARTUP_TIMEOUT=$((10#$STARTUP_TIMEOUT))
    step "Starting server on $HOST:$PORT"
    "$PYTHON" -u "$PKG_DIR/mcp_server.py" --http "$HOST:$PORT" \
        > "$WORK_DIR/server.log" 2>&1 &
    SERVER_PID=$!
    READY=0
    STARTED_AT=$SECONDS
    while [ "$((SECONDS - STARTED_AT))" -lt "$STARTUP_TIMEOUT" ]; do
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then break; fi
        if curl --max-time 1 -fsS -o "$WORK_DIR/discard" "$HEALTH_ENDPOINT" 2>"$WORK_DIR/readiness.log"; then READY=1; break; fi
        sleep 0.1
    done
    if [ "$READY" = "1" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        pass "server started (pid $SERVER_PID)"
    else
        fail "server started and became ready" "Waited $((SECONDS - STARTED_AT))s (limit ${STARTUP_TIMEOUT}s): $HEALTH_ENDPOINT"
        printf '  Bash: %s\n  Python: %s\n  curl: %s\n' "$BASH_VERSION" \
            "$(command -v "$PYTHON")" "$(type -P curl)"
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            wait "$SERVER_PID"
            printf '  Server exited with code %s\n' "$?"
            SERVER_PID=""
        fi
        echo '  Server log (last 30 lines; empty means no startup message yet):'
        tail -30 "$WORK_DIR/server.log"
        echo '  Last health probe error:'
        cat "$WORK_DIR/readiness.log" 2>/dev/null || true
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# 0. Health
# ---------------------------------------------------------------------------
step "0. Health"
HEALTH=$(curl -sS "$HEALTH_ENDPOINT" ${MCP_TOKEN:+-H "$(auth_header)"} 2>/dev/null)
if [ -n "$(json_get "$HEALTH" status)" ]; then
    pass "GET /health returns status $(json_get "$HEALTH" status)"
else
    fail "GET /health" "$HEALTH"
fi
if [ "$(json_get "$HEALTH" corpus.patterns)" != "" ]; then
    pass "health reports $(json_get "$HEALTH" corpus.patterns) patterns"
else
    fail "health reports a corpus" "$HEALTH"
fi

# ---------------------------------------------------------------------------
# 1. Initialize
# ---------------------------------------------------------------------------
step "1. Initialize the session"
INIT_BODY='{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl-test","version":"1.0.0"}},"id":1}'
INIT_ARGS=(-sS -D "$WORK_DIR/headers" -X POST
    -H 'Content-Type: application/json'
    -H 'Accept: application/json, text/event-stream')
[ -n "$MCP_TOKEN" ] && INIT_ARGS+=(-H "$(auth_header)")
INIT=$(curl "${INIT_ARGS[@]}" -d "$INIT_BODY" "$MCP_ENDPOINT" 2>/dev/null)
SESSION_ID=$(grep -i '^mcp-session-id:' "$WORK_DIR/headers" | cut -d' ' -f2 | tr -d '\r\n')
rm -f "$WORK_DIR/headers"

if [ -n "$SESSION_ID" ]; then
    pass "Mcp-Session-Id received"
else
    fail "Mcp-Session-Id received" "$INIT"
    echo; echo "Cannot continue without a session."; exit 1
fi

PROTO=$(json_get "$INIT" result.protocolVersion)
[ -n "$PROTO" ] && pass "protocol version $PROTO" || fail "protocol version" "$INIT"
[ "$(json_get "$INIT" result.serverInfo.name)" != "" ] \
    && pass "serverInfo.name = $(json_get "$INIT" result.serverInfo.name)" \
    || fail "serverInfo.name" "$INIT"

# ---------------------------------------------------------------------------
# 2. Initialized notification
# ---------------------------------------------------------------------------
step "2. Send notifications/initialized"
CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    ${MCP_TOKEN:+-H "$(auth_header)"} \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "202" ] && pass "notification accepted with 202" \
    || fail "notification accepted with 202" "got $CODE"

# ---------------------------------------------------------------------------
# 3. tools/list
# ---------------------------------------------------------------------------
step "3. List tools"
LIST=$(post '{"jsonrpc":"2.0","method":"tools/list","id":2}' "$SESSION_ID")
COUNT=$("$PYTHON" -c "
import json,sys
try: print(len(json.loads(sys.argv[1])['result']['tools']), end='')
except Exception: print(0, end='')" "$LIST" 2>/dev/null)
if [ "${COUNT:-0}" -ge 10 ]; then
    pass "$COUNT tools listed"
else
    fail "tools listed" "$LIST"
fi

for tool in search read_pattern read_section get_table_of_contents \
            list_publications get_corpus_status backlinks route entries glossary; do
    if printf '%s' "$LIST" | grep -q "\"name\": \"$tool\""; then
        pass "tool $tool present"
    else
        fail "tool $tool present"
    fi
done

# ---------------------------------------------------------------------------
# 4. tools/call
# ---------------------------------------------------------------------------
step "4. Call tools"

STATUS=$(post '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_corpus_status","arguments":{}},"id":3}' "$SESSION_ID")
if printf '%s' "$STATUS" | grep -q '"isError": false'; then
    pass "get_corpus_status returned a result"
else
    fail "get_corpus_status returned a result" "$STATUS"
fi

SEARCH=$(post '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"search","arguments":{"q":"decision","limit":3}},"id":4}' "$SESSION_ID")
if printf '%s' "$SEARCH" | grep -q 'pattern_id'; then
    pass "search returned units"
else
    fail "search returned units" "$SEARCH"
fi

READ=$(post '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"read_pattern","arguments":{"pattern_id":"PSDA.1","tier":"contract"}},"id":5}' "$SESSION_ID")
if printf '%s' "$READ" | grep -q 'returned_bytes'; then
    SIZE=$("$PYTHON" -c "
import json,sys
t=json.loads(sys.argv[1])['result']['content'][0]['text']
print(json.loads(t)['returned_bytes'], end='')" "$READ" 2>/dev/null)
    pass "read_pattern tier=contract returned ${SIZE:-?} bytes"
else
    fail "read_pattern tier=contract" "$READ"
fi

BAD=$(post '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"read_pattern","arguments":{"pattern_id":"NOPE.99"}},"id":6}' "$SESSION_ID")
if printf '%s' "$BAD" | grep -q '"isError": true'; then
    pass "unknown unit is reported as an error"
else
    fail "unknown unit is reported as an error" "$BAD"
fi

# ---------------------------------------------------------------------------
# 5. Protocol guards
# ---------------------------------------------------------------------------
step "5. Protocol guards"

CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H 'Mcp-Session-Id: not-a-real-session' \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":7}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "404" ] && pass "unknown session -> 404" \
    || fail "unknown session -> 404" "got $CODE"

CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H 'MCP-Protocol-Version: 1999-01-01' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":8}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "400" ] && pass "bad MCP-Protocol-Version -> 400" \
    || fail "bad MCP-Protocol-Version -> 400" "got $CODE"

CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H 'Origin: https://example.com' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":9}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "403" ] && pass "foreign Origin -> 403" \
    || fail "foreign Origin -> 403" "got $CODE"

CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d 'this is not json' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "400" ] && pass "malformed JSON -> 400" \
    || fail "malformed JSON -> 400" "got $CODE"

CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -m 5 "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "405" ] && pass "GET /mcp -> 405 (no server streams)" \
    || fail "GET /mcp -> 405" "got $CODE"

# ---------------------------------------------------------------------------
# 6. Terminate
# ---------------------------------------------------------------------------
step "6. Terminate the session"
CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -X DELETE \
    -H "Mcp-Session-Id: $SESSION_ID" \
    ${MCP_TOKEN:+-H "$(auth_header)"} \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "204" ] && pass "DELETE -> 204" || fail "DELETE -> 204" "got $CODE"

CODE=$(curl -sS -o "$WORK_DIR/discard" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":10}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "404" ] && pass "session is gone after DELETE" \
    || fail "session is gone after DELETE" "got $CODE"

# ---------------------------------------------------------------------------
printf '\n%s\n' "============================================"
printf 'Results: %d passed, %d failed\n' "$PASSED" "$FAILED"
printf '%s\n' "============================================"
[ "$FAILED" -eq 0 ] || exit 1
exit 0
