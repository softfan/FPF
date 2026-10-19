@echo off
REM build.cmd — Rebuild every FPF + DPF skill from the local publications (Windows CMD)
REM Usage: skill-maker\build.cmd

setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..
REM Respect a PYTHON the caller already set, like build.sh and build.ps1 do.
REM Step 10 uses the same native Python; no Bash/WSL interpreter switch.
if not defined PYTHON set PYTHON=python

REM Ensure UTF-8 output for cp1251 consoles
set PYTHONIOENCODING=utf-8

cd /d "%REPO_ROOT%"

echo ============================================
echo FPF + DPF Skill Builder
echo ============================================

%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo Error: python not found
    exit /b 1
)

REM Nothing is cleared here on purpose: each skill carries a build stamp and the
REM split is skipped when nothing changed.  Delete skills for a clean rebuild.

echo [1/10] Splitting FPF Core + Library documents...
%PYTHON% skill-maker\src\skillmaker\split_fpf_spec.py split --source FPF-Spec.md --output skills\fpf --views
if errorlevel 1 (
    echo FPF split failed
    exit /b 2
)

echo.
echo [2/10] Splitting DPF Suites and standalone DPFs...
%PYTHON% skill-maker\src\skillmaker\split_dpf_spec.py split --all --views
if errorlevel 1 (
    echo DPF split failed
    exit /b 2
)

echo.
echo [3/10] Writing the skills index...
%PYTHON% skill-maker\src\skillmaker\skill_index.py
if errorlevel 1 (
    echo   X Skill index failed
    exit /b 1
)

echo.
echo [4/10] Running FPF audit...
%PYTHON% skill-maker\src\skillmaker\audit_fpf_patterns.py --source FPF-Spec.md --skill-dir skills\fpf
if errorlevel 1 echo   Warning: Audit reported issues

echo.
echo [5/10] Running tests (FPF + DPF)...
%PYTHON% skill-maker\tests\test_fpf_pipeline.py
if errorlevel 1 (
    echo FPF tests failed
    exit /b 4
)
%PYTHON% skill-maker\tests\test_dpf_pipeline.py
if errorlevel 1 (
    echo   X DPF tests failed
    exit /b 1
)

echo.
echo [6/10] Checking framework decomposition against the publisher catalogue...
%PYTHON% skill-maker\tests\test_frameworks.py
if errorlevel 1 (
    echo   X Framework tests failed
    exit /b 1
)

echo.
echo [7/10] Checking the generic skill builder...
%PYTHON% skill-maker\tests\test_build_generic.py
if errorlevel 1 (
    echo   X Generic builder tests failed
    exit /b 1
)

echo.
echo [8/10] Checking the MCP server...
%PYTHON% skill-maker\tests\test_mcp_server.py
if errorlevel 1 (
    echo   X MCP server tests failed
    exit /b 1
)

echo.
echo [9/10] Checking the derived retrieval layer...
%PYTHON% skill-maker\tests\test_derived.py
if errorlevel 1 (
    echo   X Derived-layer tests failed
    exit /b 1
)

echo.
echo [10/10] Checking the HTTP transport...
%PYTHON% skill-maker\tests\test_hardening.py
if errorlevel 1 (
    echo   X Hardening tests failed
    exit /b 1
)
%PYTHON% skill-maker\tests\test_mcp_http.py
if errorlevel 1 (
    echo   X HTTP transport tests failed
    exit /b 1
)

echo.
echo Build summary
echo --------------------------------------------
%PYTHON% skill-maker\src\skillmaker\split_fpf_spec.py stats
%PYTHON% skill-maker\src\skillmaker\split_dpf_spec.py stats
echo ============================================

endlocal
