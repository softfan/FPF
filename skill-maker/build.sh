#!/usr/bin/env bash
# build.sh — Rebuild every FPF + DPF skill from the local publications
# Usage: ./skill-maker/build.sh
# Or from repo root: bash skill-maker/build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON="${PYTHON:-python3}"

cd "$REPO_ROOT"

echo "============================================"
echo "FPF + DPF Skill Builder"
echo "============================================"

# Check Python
if ! command -v "$PYTHON" &>/dev/null; then
    echo "Error: $PYTHON not found. Set PYTHON env var."
    exit 1
fi

# Skills: FPF Core, the four DPF Suites, the ten standalone DPFs.
SKILLS=(
    fpf
    engineering-suite management-suite foundational-thinking-suite
    human-capability-engineering-suite
    decision-design research-methods explanation-design narrativization
    implementation-facilitation economic-reasoning financial-modeling
    defense-transmission embodied-rhythmics music-dance-practice
)

# Nothing is cleared here on purpose.  Each skill carries a build stamp
# (.<skill>_build.json) naming the engine and source digests it was built from;
# when both match and every manifest file exists, the split is skipped.  Delete
# skills/ for a clean rebuild.

echo ""
echo "[1/10] Splitting FPF Core + Library documents..."
"$PYTHON" skill-maker/src/skillmaker/split_fpf_spec.py split \
    --source FPF-Spec.md \
    --output skills/fpf \
    --views

echo ""
echo "[2/10] Splitting DPF Suites and standalone DPFs..."
"$PYTHON" skill-maker/src/skillmaker/split_dpf_spec.py split --all --views

echo ""
echo "[3/10] Writing the skills index (skills/README.md, skills/index.json)..."
"$PYTHON" skill-maker/src/skillmaker/skill_index.py

echo ""
echo "[4/10] Running FPF audit..."
"$PYTHON" skill-maker/src/skillmaker/audit_fpf_patterns.py \
    --source FPF-Spec.md \
    --skill-dir skills/fpf || echo "  ⚠ Audit reported issues"

echo ""
echo "[5/10] Running tests (FPF + DPF)..."
"$PYTHON" skill-maker/tests/test_fpf_pipeline.py || {
    echo "  ✗ FPF tests failed"
    exit 1
}
"$PYTHON" skill-maker/tests/test_dpf_pipeline.py || {
    echo "  ✗ DPF tests failed"
    exit 1
}

echo ""
echo "[6/10] Checking framework decomposition against the publisher catalogue..."
"$PYTHON" skill-maker/tests/test_frameworks.py || {
    echo "  ✗ Framework tests failed"
    exit 1
}

echo ""
echo "[7/10] Checking the generic skill builder..."
"$PYTHON" skill-maker/tests/test_build_generic.py || {
    echo "  ✗ Generic builder tests failed"
    exit 1
}

echo ""
echo "[8/10] Checking the MCP server..."
"$PYTHON" skill-maker/tests/test_mcp_server.py || {
    echo "  ✗ MCP server tests failed"
    exit 1
}

echo ""
echo "[9/10] Checking the derived retrieval layer..."
"$PYTHON" skill-maker/tests/test_derived.py || {
    echo "  ✗ Derived-layer tests failed"
    exit 1
}

echo ""
echo "[10/10] Checking the HTTP transport..."
bash skill-maker/tests/test-mcp-http.sh || {
    echo "  ✗ HTTP transport tests failed"
    exit 1
}

echo ""
echo "Build summary"
echo "--------------------------------------------"
"$PYTHON" skill-maker/src/skillmaker/split_fpf_spec.py stats
"$PYTHON" skill-maker/src/skillmaker/split_dpf_spec.py stats
echo "============================================"
