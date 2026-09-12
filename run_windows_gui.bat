@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3, 14)" >nul 2>nul
  if errorlevel 1 (
    echo The existing .venv does not use Python 3.14.
    echo Remove or rename .venv, then run this launcher again.
    pause
    exit /b 1
  )
) else (
  py -3.14 -m venv .venv
  if errorlevel 1 (
    echo Python 3.14 is required.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
