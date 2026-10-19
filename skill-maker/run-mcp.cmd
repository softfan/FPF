@echo off
setlocal
REM Keep stdout exclusively for MCP. Respect the caller's native interpreter.
if not defined PYTHON set PYTHON=python
set PYTHONIOENCODING=utf-8
"%PYTHON%" "%~dp0run-mcp.py" %*
exit /b %ERRORLEVEL%
