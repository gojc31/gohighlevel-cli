@echo off
REM GHL CLI wrapper for Windows - runs the CLI from the local venv.
REM .env loading lives in Python (cli_anything/_env.py), not here.
setlocal disabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

set "PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%SCRIPT_DIR%.venv\bin\python.exe"
if not exist "%PY%" (
  echo No virtualenv found. Run install.sh first. 1>&2
  exit /b 1
)

"%PY%" -m cli_anything.gohighlevel %*
exit /b %ERRORLEVEL%
