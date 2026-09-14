@echo off
REM GHL CLI wrapper for Windows - activates venv and loads .env
setlocal disabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%SCRIPT_DIR%.env") do call :setenvvar "%%A" %%B
)

"%SCRIPT_DIR%.venv\Scripts\python.exe" -m cli_anything.gohighlevel %*
exit /b %ERRORLEVEL%

:setenvvar
set "_key=%~1"
if "%_key%"=="" goto :eof
set "_val=%~2"
if "%_val:~0,1%"=="'" if "%_val:~-1%"=="'" set "_val=%_val:~1,-1%"
set "%_key%=%_val%"
goto :eof
