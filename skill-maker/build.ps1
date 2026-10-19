# build.ps1 — Rebuild every FPF + DPF skill from the local publications
# Usage: .\skill-maker\build.ps1
# Or: powershell -File skill-maker\build.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

# Ensure UTF-8 output for cp1251 consoles (fix Unicode print crashes)
$env:PYTHONIOENCODING = "utf-8"

# Step 10 runs under bash, which picks its interpreter from PYTHON; export the
# one this script uses so the HTTP walkthrough starts the same server.
$env:PYTHON = $Python

Set-Location $RepoRoot

Write-Host "============================================"
Write-Host "FPF + DPF Skill Builder"
Write-Host "============================================"

# Check Python
try {
    & $Python --version | Out-Null
} catch {
    Write-Host "Error: $Python not found. Set PYTHON env var."
    exit 1
}

# Skills: FPF Core, the four DPF Suites, the ten standalone DPFs.
$skills = @(
    "fpf",
    "engineering-suite", "management-suite", "foundational-thinking-suite",
    "human-capability-engineering-suite",
    "decision-design", "research-methods", "explanation-design", "narrativization",
    "implementation-facilitation", "economic-reasoning", "financial-modeling",
    "defense-transmission", "embodied-rhythmics", "music-dance-practice"
)

# Nothing is cleared here on purpose: each skill carries a build stamp and the
# split is skipped when nothing changed.  Delete skills/ for a clean rebuild.

Write-Host ""
Write-Host "[1/10] Splitting FPF Core + Library documents..."
& $Python skill-maker/src/skillmaker/split_fpf_spec.py split `
    --source FPF-Spec.md `
    --output skills/fpf `
    --views
if ($LASTEXITCODE -ne 0) { Write-Host "FPF split failed"; exit 2 }

Write-Host ""
Write-Host "[2/10] Splitting DPF Suites and standalone DPFs..."
& $Python skill-maker/src/skillmaker/split_dpf_spec.py split --all --views
if ($LASTEXITCODE -ne 0) { Write-Host "DPF split failed"; exit 2 }

Write-Host ""
Write-Host "[3/10] Writing the skills index..."
& $Python skill-maker/src/skillmaker/skill_index.py
if ($LASTEXITCODE -ne 0) { Write-Host "  X Skill index failed"; exit 1 }

Write-Host ""
Write-Host "[4/10] Running FPF audit..."
& $Python skill-maker/src/skillmaker/audit_fpf_patterns.py `
    --source FPF-Spec.md `
    --skill-dir skills/fpf
if ($LASTEXITCODE -ne 0) { Write-Host "  Warning: Audit reported issues" }

Write-Host ""
Write-Host "[5/10] Running tests (FPF + DPF)..."
& $Python skill-maker/tests/test_fpf_pipeline.py
if ($LASTEXITCODE -ne 0) { Write-Host "FPF tests failed"; exit 4 }
& $Python skill-maker/tests/test_dpf_pipeline.py
if ($LASTEXITCODE -ne 0) { Write-Host "  X DPF tests failed"; exit 1 }

Write-Host ""
Write-Host "[6/10] Checking framework decomposition against the publisher catalogue..."
& $Python skill-maker/tests/test_frameworks.py
if ($LASTEXITCODE -ne 0) { Write-Host "  X Framework tests failed"; exit 1 }

Write-Host ""
Write-Host "[7/10] Checking the generic skill builder..."
& $Python skill-maker/tests/test_build_generic.py
if ($LASTEXITCODE -ne 0) { Write-Host "  X Generic builder tests failed"; exit 1 }

Write-Host ""
Write-Host "[8/10] Checking the MCP server..."
& $Python skill-maker/tests/test_mcp_server.py
if ($LASTEXITCODE -ne 0) { Write-Host "  X MCP server tests failed"; exit 1 }

Write-Host ""
Write-Host "[9/10] Checking the derived retrieval layer..."
& $Python skill-maker/tests/test_derived.py
if ($LASTEXITCODE -ne 0) { Write-Host "  X Derived-layer tests failed"; exit 1 }

Write-Host ""
Write-Host "[10/10] Checking the HTTP transport..."
if ($null -eq (Get-Command bash -ErrorAction SilentlyContinue)) {
    Write-Host "  - skipped: bash not found (Git Bash or WSL runs the curl walkthrough)"
} else {
    & bash skill-maker/tests/test-mcp-http.sh
    if ($LASTEXITCODE -ne 0) { Write-Host "  X HTTP transport tests failed"; exit 1 }
}

Write-Host ""
Write-Host "Build summary"
Write-Host "--------------------------------------------"
& $Python skill-maker/src/skillmaker/split_fpf_spec.py stats
& $Python skill-maker/src/skillmaker/split_dpf_spec.py stats
Write-Host "============================================"
