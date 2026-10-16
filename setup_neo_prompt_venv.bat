@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "LAUNCHER_DIR=%~dp0"
set "APP_DIR=%LAUNCHER_DIR%"
echo.
echo ======================================
echo    NEO PROMPT - SETUP
echo ======================================
echo.
if not exist "%APP_DIR%neo_prompt\cli.py" (
  if exist "%LAUNCHER_DIR%Neo_Prompt\neo_prompt\cli.py" (
    set "APP_DIR=%LAUNCHER_DIR%Neo_Prompt\"
  ) else (
    echo [ERROR] Cannot find neo_prompt\cli.py next to the setup launcher.
    echo Extract the complete Neo Prompt archive into a folder you choose.
    pause
    exit /b 1
  )
)
if not exist "%APP_DIR%requirements.txt" (
  echo [ERROR] Missing requirements.txt. Re-extract the complete ZIP.
  pause
  exit /b 1
)
set "VENV_DIR=%APP_DIR%.venv"
if exist "%LAUNCHER_DIR%.venv\Scripts\python.exe" set "VENV_DIR=%LAUNCHER_DIR%.venv"
echo [Neo Prompt] App folder: "%APP_DIR%"
echo [Neo Prompt] Environment: "%VENV_DIR%"
if not exist "%VENV_DIR%\Scripts\python.exe" (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 -m venv "%VENV_DIR%"
  ) else (
    python -m venv "%VENV_DIR%"
  )
  if errorlevel 1 (
    echo [ERROR] Could not create a virtual environment.
    echo Install Python 3.10 or newer and enable its launcher/PATH.
    pause
    exit /b 1
  )
)
cd /d "%APP_DIR%"
if errorlevel 1 (
  echo [ERROR] Could not enter the app directory.
  pause
  exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed installing Neo Prompt dependencies.
  pause
  exit /b 1
)
set "PYTHONPATH=%APP_DIR%;%PYTHONPATH%"
echo [Neo Prompt] Checking complete installation...
"%VENV_DIR%\Scripts\python.exe" -m neo_prompt.cli --help
if errorlevel 1 (
  echo [ERROR] Installed packages or Neo Prompt import are not working.
  pause
  exit /b 1
)
echo.
echo [SUCCESS] Setup complete. Double-click run_neo_prompt.bat.
pause
endlocal
