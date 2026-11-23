@echo off
setlocal
cd /d "%~dp0"
if exist "runtime\python.exe" (
  "runtime\python.exe" studio.py serve --open
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" studio.py serve --open
) else (
  python studio.py serve --open
)
if errorlevel 1 pause
