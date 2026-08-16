@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found.
  echo Install current Python 3.14 and enable the Python launcher.
  pause
  exit /b 1
)

py -3.14 -c "import sys; print(sys.version)" >nul 2>nul
if errorlevel 1 (
  echo Python 3.14 is required for the current development toolchain.
  pause
  exit /b 1
)

if not exist ".venv" (
  py -3.14 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

python -m pytest
if errorlevel 1 exit /b 1
ruff check playstore_app_audit tests main.py
if errorlevel 1 exit /b 1

python -c "from app_icon import generate_windows_ico; print(generate_windows_ico('.'))"
pyside6-deploy main.py --name PlayStoreAppAudit --init
python -c "from configparser import ConfigParser; from pathlib import Path; p=ConfigParser(); p.read('pysidedeploy.spec'); p['app']['exec_directory']=str(Path('dist').resolve()); p['app']['icon']=str(Path('app_icon.ico').resolve()); p['nuitka']['mode']='onefile'; p['nuitka']['extra_args']='--quiet --noinclude-qt-translations --windows-console-mode=disable --nofollow-import-to=PIL --assume-yes-for-downloads'; f=open('pysidedeploy.spec','w',encoding='utf-8'); p.write(f); f.close()"
pyside6-deploy -c pysidedeploy.spec -f
if errorlevel 1 exit /b 1

echo.
echo Build completed. Check the dist folder for the deployed executable.
pause
