#!/usr/bin/env bash
# Run in the foreground. exec preserves stdio, signals and the server exit code.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$SCRIPT_DIR/run-mcp.py" "$@"
