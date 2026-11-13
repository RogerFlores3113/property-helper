@echo off
rem Double-click this file to start Property Helper on Windows.
rem If Windows shows "Windows protected your PC", press More info, then Run anyway.
cd /d "%~dp0"

rem The app prints its own plain lines and keeps the technical log in a file.
set "PROPHELPER_QUIET=1"
set "UV_NO_PROGRESS=1"
set "STEP=starting the app"

set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
  set "STEP=installing the helper called uv"
  echo First time setup: installing a small helper called uv. This needs internet and takes about a minute.
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
  where uv >nul 2>nul
  if errorlevel 1 goto problem
)

if not exist ".venv" echo The first time can take about a minute while it sets itself up.
uv run --quiet prophelper
if errorlevel 1 goto problem
goto end

:problem
echo.
echo Something went wrong. Nothing was lost, and your places are safe.
echo This step failed: %STEP%.
if "%STEP%"=="installing the helper called uv" (
  echo Check your internet connection, close this window and double-click again.
) else (
  echo Close this window and double-click Start Property Helper again to try once more.
)
echo Your places are kept in a folder of their own, so downloading a newer copy of this app is safe too.
pause

:end
