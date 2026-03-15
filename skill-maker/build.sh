#!/usr/bin/env bash
# build.sh — Build FPF skill from spec
# Usage: ./skill-maker/build.sh
# Or from repo root: bash skill-maker/build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON="${PYTHON:-python3}"

cd "$REPO_ROOT"

echo "============================================"
echo "FPF Skill Builder"
echo "============================================"

# Check Python
if ! command -v "$PYTHON" &>/dev/null; then
    echo "Error: $PYTHON not found. Set PYTHON env var."
    exit 1
fi

echo ""
echo "[1/4] Splitting spec..."
"$PYTHON" skill-maker/split_fpf_spec.py split \
    --source FPF-Spec.md \
    --output skills/fpf

echo ""
echo "[2/4] Running audit..."
"$PYTHON" skill-maker/audit_fpf_patterns.py \
    --source FPF-Spec.md \
    --skill-dir skills/fpf || echo "  ⚠ Audit reported issues"

echo ""
echo "[3/4] Running tests..."
"$PYTHON" skill-maker/test_fpf_pipeline.py || {
    echo "  ✗ Tests failed"
    exit 1
}

echo ""
echo "[4/4] Done!"
echo "  Skill directory: skills/fpf/"
echo "  Pattern count: $(find skills/fpf/reference/fpf-patterns -name '*.md' ! -name 'index.md' | wc -l | tr -d ' ')"
echo "============================================"
