@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
)
if not exist ".venv\Scripts\python.exe" (
  echo Please install Python 3.11 or 3.12, then run this file again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check your internet connection and Python version.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8000 in your browser. Keep this window open.
".venv\Scripts\python.exe" app.py
pause
