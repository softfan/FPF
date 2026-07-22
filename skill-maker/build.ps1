# build.ps1 — Build FPF skill from spec (Windows PowerShell)
# Usage: .\skill-maker\build.ps1
# Or: powershell -File skill-maker\build.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

# Ensure UTF-8 output for cp1251 consoles (fix Unicode print crashes)
$env:PYTHONIOENCODING = "utf-8"

Set-Location $RepoRoot

Write-Host "============================================"
Write-Host "FPF Skill Builder"
Write-Host "============================================"

# Check Python
try {
    & $Python --version | Out-Null
} catch {
    Write-Host "Error: $Python not found. Set PYTHON env var."
    exit 1
}

# Remove hash cache to force fresh writes and avoid cross-platform cache poisoning
$CacheFile = Join-Path -Path $RepoRoot -ChildPath "skills\fpf\.fpf_hashes.json"
if (Test-Path $CacheFile) {
    Remove-Item -Path $CacheFile -Force
    Write-Host "(cleared hash cache for cross-platform safety)"
}

Write-Host ""
Write-Host "[1/4] Splitting spec..."
& $Python skill-maker/split_fpf_spec.py split `
    --source FPF-Spec.md `
    --output skills/fpf
if ($LASTEXITCODE -ne 0) { Write-Host "Split failed"; exit 2 }

Write-Host ""
Write-Host "[2/4] Running audit..."
& $Python skill-maker/audit_fpf_patterns.py `
    --source FPF-Spec.md `
    --skill-dir skills/fpf
if ($LASTEXITCODE -ne 0) { Write-Host "  Warning: Audit reported issues" }

Write-Host ""
Write-Host "[3/4] Running tests..."
& $Python skill-maker/test_fpf_pipeline.py
if ($LASTEXITCODE -ne 0) { Write-Host "Tests failed"; exit 4 }

Write-Host ""
Write-Host "[4/4] Done!"
$patternCount = (Get-ChildItem skills/fpf/reference/fpf-patterns/*.md |
    Where-Object { $_.Name -ne "index.md" }).Count
Write-Host "  Skill directory: skills/fpf/"
Write-Host "  Pattern count: $patternCount"
Write-Host "============================================"
