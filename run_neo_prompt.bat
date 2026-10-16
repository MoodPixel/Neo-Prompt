@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "LAUNCHER_DIR=%~dp0"
set "APP_DIR=%LAUNCHER_DIR%"
echo.
echo ======================================
echo    NEO PROMPT - CREATIVE LANGUAGE STUDIO
echo ======================================
echo.

rem The application files and this launcher should be in the same folder.
rem Support exactly one extra Neo_Prompt folder when the ZIP tool nests it.
if not exist "%APP_DIR%neo_prompt\cli.py" (
  if exist "%LAUNCHER_DIR%Neo_Prompt\neo_prompt\cli.py" (
    set "APP_DIR=%LAUNCHER_DIR%Neo_Prompt\"
  ) else (
    echo [ERROR] The Neo Prompt Python package is missing.
    echo [EXPECTED] Neo_Prompt\neo_prompt\cli.py
    echo [ACTUAL] Launcher folder: "%LAUNCHER_DIR%"
    echo.
    echo Extract the COMPLETE Neo Prompt ZIP into the parent directory.
    echo Extract the complete archive to a folder you choose, then run this launcher.
    echo Do not copy a launcher from an earlier ZIP by itself.
    pause
    exit /b 1
  )
)
if not exist "%APP_DIR%neo_prompt\__init__.py" (
  echo [ERROR] Incomplete Neo Prompt package in "%APP_DIR%neo_prompt".
  pause
  exit /b 1
)
set "PYTHON_EXE=%APP_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%LAUNCHER_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] The standalone Python environment is missing.
  echo Run setup_neo_prompt_venv.bat first, then start again.
  echo App directory: "%APP_DIR%"
  pause
  exit /b 1
)

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo [ERROR] Cannot enter application directory: "%APP_DIR%".
  pause
  exit /b 1
)
rem Explicit import root prevents an installed Python/venv startup path from hiding the local package.
set "PYTHONPATH=%APP_DIR%;%PYTHONPATH%"
echo [Neo Prompt] App folder: "%APP_DIR%"
echo [Neo Prompt] Python: "%PYTHON_EXE%"
echo [Neo Prompt] Checking package import...
"%PYTHON_EXE%" -c "import importlib.util,sys; m=importlib.util.find_spec('neo_prompt'); print('[Neo Prompt] Python package:', m.origin if m else 'NOT FOUND'); sys.exit(0 if m else 1)"
if errorlevel 1 (
  echo [ERROR] The local neo_prompt package is still not importable.
  echo Make sure the Python source directory has not been moved or deleted.
  pause
  exit /b 1
)
echo [Neo Prompt] Starting at http://127.0.0.1:7891
"%PYTHON_EXE%" -m neo_prompt.cli
if errorlevel 1 (
  echo.
  echo [ERROR] Neo Prompt stopped. See the Python error above.
  echo If dependencies are missing, run setup_neo_prompt_venv.bat again.
  pause
  exit /b 1
)
endlocal
