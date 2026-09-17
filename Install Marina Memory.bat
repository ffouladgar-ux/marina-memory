@echo off
REM Double-click this file to install Marina Memory on Windows.
REM Best effort: the macOS path is the one that has been verified.
cd /d "%~dp0"

echo Marina Memory: automatic installer
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo Installing uv ^(small tool manager^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
)

set "UV_TOOL_BIN_DIR=%USERPROFILE%\.local\bin"
set "PATH=%UV_TOOL_BIN_DIR%;%PATH%"

uv tool install --force .
if errorlevel 1 goto failed

mm init
if errorlevel 1 goto failed

mm connect-claude
if errorlevel 1 goto failed

mm doctor
echo.
echo Almost done. Quit Claude completely and reopen it, then paste the
echo instructions from CLAUDE-INSTRUCTIONS.md into Settings, Profile,
echo Custom Instructions.
goto end

:failed
echo.
echo Something did not work. Copy this window and send it to Fadi.

:end
echo.
pause
