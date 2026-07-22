@echo off
REM build.cmd — Build FPF skill from spec (Windows CMD)
REM Usage: skill-maker\build.cmd

setlocal

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..
set PYTHON=python

REM Ensure UTF-8 output for cp1251 consoles
set PYTHONIOENCODING=utf-8

cd /d "%REPO_ROOT%"

echo ============================================
echo FPF Skill Builder
echo ============================================

%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo Error: python not found
    exit /b 1
)

REM Remove hash cache to force fresh writes (cross-platform safety)
if exist "%REPO_ROOT%\skills\fpf\.fpf_hashes.json" (
    del "%REPO_ROOT%\skills\fpf\.fpf_hashes.json"
    echo (cleared hash cache for cross-platform safety)
)

echo.
echo [1/4] Splitting spec...
%PYTHON% skill-maker\split_fpf_spec.py split --source FPF-Spec.md --output skills\fpf
if errorlevel 1 (
    echo Split failed
    exit /b 2
)

echo.
echo [2/4] Running audit...
%PYTHON% skill-maker\audit_fpf_patterns.py --source FPF-Spec.md --skill-dir skills\fpf
if errorlevel 1 echo   Warning: Audit reported issues

echo.
echo [3/4] Running tests...
%PYTHON% skill-maker\test_fpf_pipeline.py
if errorlevel 1 (
    echo Tests failed
    exit /b 4
)

echo.
echo [4/4] Done!
echo   Skill directory: skills\fpf\
echo ============================================

endlocal
