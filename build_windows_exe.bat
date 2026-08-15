@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python non trovato.
  echo Installa Python 3.11 o successivo e seleziona "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv" (
  py -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
python -c "from app_icon import generate_windows_ico; print(generate_windows_ico('.'))"

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name PlayStoreAppAudit-CustomTkinter ^
  --icon app_icon.ico ^
  --collect-all google_play_scraper ^
  --collect-all bs4 ^
  --collect-all lxml ^
  --collect-all customtkinter ^
  playstore_audit_customtkinter_launcher.py

echo.
echo Build CustomTkinter completata.
echo EXE: %CD%\dist\PlayStoreAppAudit-CustomTkinter.exe
pause
