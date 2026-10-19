# Run the MCP server using native Python; no Bash/WSL dependency.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$env:PYTHONIOENCODING = "utf-8"
& $Python (Join-Path $ScriptDir "run-mcp.py") @args
exit $LASTEXITCODE
