@echo off
setlocal EnableExtensions
REM Double-click this file to install Marina Memory on Windows.
REM It installs everything it needs, then keeps the window open so you can read the result.

cd /d "%~dp0" || goto :failed

echo ================================================================
echo  Marina Memory: automatic installer
echo  This window shows progress. First run takes 2 to 5 minutes.
echo ================================================================
echo.

set "UV_TOOL_BIN_DIR=%USERPROFILE%\.local\bin"
set "UV_TOOL_DIR=%USERPROFILE%\.local\share\uv\tools"
set "PATH=%UV_TOOL_BIN_DIR%;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
  echo -^> Installing 'uv' ^(a small tool manager, about 30 seconds^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  if errorlevel 1 (
    echo.
    echo Could not install uv automatically.
    echo On a work or school PC, this is usually a security policy.
    echo Ask Fadi to run this in PowerShell for you, then run this installer again:
    echo    irm https://astral.sh/uv/install.ps1 ^| iex
    goto :failed
  )
)

where uv >nul 2>nul
if errorlevel 1 (
  echo uv was installed but is not on PATH yet.
  echo Close this window and double-click the installer again.
  goto :failed
)

echo -^> Installing marina-memory ^(downloads Python on first run^)...
uv tool install --force .
if errorlevel 1 goto :failed

where mm >nul 2>nul
if errorlevel 1 (
  echo.
  echo 'mm' was not found after installing. It should be in:
  echo    %UV_TOOL_BIN_DIR%
  goto :failed
)

echo.
echo -^> Creating your memory vault ^(plain Markdown files you own^)...
mm init
if errorlevel 1 goto :failed

echo.
echo -^> Connecting it to Claude Desktop...
mm connect-claude
if errorlevel 1 goto :failed

echo.
echo -^> Verifying...
mm doctor
if errorlevel 1 goto :failed

echo.
echo ================================================================
echo  Almost done. Two steps left, once:
echo.
echo   1. Quit Claude completely: right-click the Claude icon next to
echo      the clock ^(system tray^) and choose Quit. Closing the window
echo      is not enough, it will not reload.
echo   2. Reopen Claude, then paste the instructions from
echo      CLAUDE-INSTRUCTIONS.md into Settings, Profile,
echo      Custom Instructions.
echo.
echo  Then just talk to it normally.
echo ================================================================
goto :end

:failed
echo.
echo ================================================================
echo  Setup did not finish.
echo.
echo  Select the text in this window with the mouse, copy it, and
echo  send it to Fadi. Nothing is broken and it is safe to re-run.
echo ================================================================

:end
echo.
pause
