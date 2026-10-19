#!/usr/bin/env bash
# test-mcp-http.sh -- end-to-end check of the Streamable HTTP transport.
#
# Runs the server, walks the protocol by hand with curl, and asserts each step.
# Nothing here needs a client library: the point is to prove the endpoint works
# from a shell, which is the hardest case to fake.
#
# Usage:
#   bash skill-maker/test-mcp-http.sh              # start, test, stop
#   MCP_ENDPOINT=http://127.0.0.1:8765/mcp bash skill-maker/test-mcp-http.sh
#   MCP_TOKEN=... bash skill-maker/test-mcp-http.sh   # when auth is required
#
# Exit code: 0 when every assertion passes.

set -u

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-8765}"
MCP_ENDPOINT="${MCP_ENDPOINT:-http://$HOST:$PORT/mcp}"
MCP_TOKEN="${MCP_TOKEN:-}"
START_SERVER="${START_SERVER:-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON="${PYTHON:-python3}"

# Windows Python installs "python", not "python3".  The build scripts export
# PYTHON, so this only matters when the walkthrough is run by hand.
if ! command -v "$PYTHON" >/dev/null 2>&1 && command -v python >/dev/null 2>&1; then
    PYTHON=python
fi

PASSED=0
FAILED=0
SERVER_PID=""

pass() { PASSED=$((PASSED + 1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { FAILED=$((FAILED + 1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; [ -n "${2:-}" ] && printf '       %s\n' "$2"; }
step() { printf '\n%s\n' "$1"; }

cleanup() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null
        wait "$SERVER_PID" 2>/dev/null
    fi
}
trap cleanup EXIT

auth_header() {
    if [ -n "$MCP_TOKEN" ]; then printf 'Authorization: Bearer %s' "$MCP_TOKEN"; fi
}

# post BODY -> prints response body, sets HTTP_CODE
post() {
    local body="$1" session="${2:-}"
    local args=(-sS -o /tmp/mcp_body.$$ -w '%{http_code}' -X POST
        -H 'Content-Type: application/json'
        -H 'Accept: application/json, text/event-stream')
    [ -n "$MCP_TOKEN" ] && args+=(-H "$(auth_header)")
    [ -n "$session" ] && args+=(-H "Mcp-Session-Id: $session")
    HTTP_CODE=$(curl "${args[@]}" -d "$body" "$MCP_ENDPOINT" 2>/dev/null)
    cat /tmp/mcp_body.$$ 2>/dev/null
    rm -f /tmp/mcp_body.$$
}

json_get() { printf '%s' "$1" | "$PYTHON" -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print(''); raise SystemExit
for k in sys.argv[1].split('.'):
    if isinstance(d,list): d=d[int(k)]
    elif isinstance(d,dict): d=d.get(k)
    else: d=None
    if d is None: break
print('' if d is None else d)
" "$2" 2>/dev/null; }

# ---------------------------------------------------------------------------
# Start the server when we are testing a local build.
# ---------------------------------------------------------------------------
if [ "$START_SERVER" = "1" ]; then
    step "Starting server on $HOST:$PORT"
    "$PYTHON" "$SCRIPT_DIR/mcp_server.py" --http "$HOST:$PORT" \
        > /tmp/mcp_http_$$.log 2>&1 &
    SERVER_PID=$!
    for _ in $(seq 1 50); do
        if curl -sS -o /dev/null "http://$HOST:$PORT/health" 2>/dev/null; then break; fi
        sleep 0.1
    done
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        pass "server started (pid $SERVER_PID)"
    else
        fail "server started" "$(tail -3 /tmp/mcp_http_$$.log)"
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# 0. Health
# ---------------------------------------------------------------------------
step "0. Health"
HEALTH=$(curl -sS "http://$HOST:$PORT/health" 2>/dev/null)
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
INIT_ARGS=(-sS -D /tmp/mcp_head.$$ -X POST
    -H 'Content-Type: application/json'
    -H 'Accept: application/json, text/event-stream')
[ -n "$MCP_TOKEN" ] && INIT_ARGS+=(-H "$(auth_header)")
INIT=$(curl "${INIT_ARGS[@]}" -d "$INIT_BODY" "$MCP_ENDPOINT" 2>/dev/null)
SESSION_ID=$(grep -i '^mcp-session-id:' /tmp/mcp_head.$$ | cut -d' ' -f2 | tr -d '\r\n')
rm -f /tmp/mcp_head.$$

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
CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
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
try: print(len(json.loads(sys.argv[1])['result']['tools']))
except Exception: print(0)" "$LIST" 2>/dev/null)
if [ "${COUNT:-0}" -ge 14 ]; then
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
print(json.loads(t)['returned_bytes'])" "$READ" 2>/dev/null)
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

CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H 'Mcp-Session-Id: not-a-real-session' \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":7}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "404" ] && pass "unknown session -> 404" \
    || fail "unknown session -> 404" "got $CODE"

CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H 'MCP-Protocol-Version: 1999-01-01' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":8}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "400" ] && pass "bad MCP-Protocol-Version -> 400" \
    || fail "bad MCP-Protocol-Version -> 400" "got $CODE"

CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H 'Origin: https://example.com' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":9}' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "403" ] && pass "foreign Origin -> 403" \
    || fail "foreign Origin -> 403" "got $CODE"

CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d 'this is not json' \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "400" ] && pass "malformed JSON -> 400" \
    || fail "malformed JSON -> 400" "got $CODE"

CODE=$(curl -sS -o /dev/null -w '%{http_code}' -m 5 "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "405" ] && pass "GET /mcp -> 405 (no server streams)" \
    || fail "GET /mcp -> 405" "got $CODE"

# ---------------------------------------------------------------------------
# 6. Terminate
# ---------------------------------------------------------------------------
step "6. Terminate the session"
CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE \
    -H "Mcp-Session-Id: $SESSION_ID" \
    ${MCP_TOKEN:+-H "$(auth_header)"} \
    "$MCP_ENDPOINT" 2>/dev/null)
[ "$CODE" = "204" ] && pass "DELETE -> 204" || fail "DELETE -> 204" "got $CODE"

CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
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
