@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo === Play Store App Audit Windows x64 standalone build ===
echo.

set "PYTHON="

if defined PLAYSTORE_RELEASE_PYTHON (
  if exist "%PLAYSTORE_RELEASE_PYTHON%" (
    set "PYTHON=%PLAYSTORE_RELEASE_PYTHON%"
  ) else (
    echo PLAYSTORE_RELEASE_PYTHON does not exist:
    echo %PLAYSTORE_RELEASE_PYTHON%
    exit /b 1
  )
)

if not defined PYTHON if exist "dist\release314env\Scripts\python.exe" (
  set "PYTHON=%CD%\dist\release314env\Scripts\python.exe"
)

if not defined PYTHON if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import platform, sys; assert sys.version_info[:2] == (3, 14); assert platform.machine().upper() in {'AMD64','X86_64'}" >nul 2>nul
  if not errorlevel 1 set "PYTHON=%CD%\.venv\Scripts\python.exe"
)

if not defined PYTHON (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Native Windows x64 Python 3.14 is required.
    echo Install Python 3.14 with the Windows Python launcher.
    exit /b 1
  )

  py -3.14 -c "import platform, sys; assert sys.version_info[:2] == (3, 14); assert platform.machine().upper() in {'AMD64','X86_64'}" >nul 2>nul
  if errorlevel 1 (
    echo Native Windows x64 Python 3.14 is required.
    exit /b 1
  )

  if exist ".venv" (
    echo The existing .venv is not a native Windows x64 Python 3.14 environment.
    echo Remove or rename it, or set PLAYSTORE_RELEASE_PYTHON to a valid Python 3.14 x64 executable.
    exit /b 1
  )

  py -3.14 -m venv .venv
  if errorlevel 1 exit /b 1
  set "PYTHON=%CD%\.venv\Scripts\python.exe"
)

echo Release Python:
echo %PYTHON%
"%PYTHON%" -c "import platform, sys; print(sys.version); print(platform.machine()); assert sys.version_info[:2] == (3, 14); assert platform.machine().upper() in {'AMD64','X86_64'}"
if errorlevel 1 exit /b 1

echo.
echo === Install/update build dependencies ===
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%PYTHON%" -m pip install -r requirements-dev.txt "Nuitka==4.2.1"
if errorlevel 1 exit /b 1

echo.
echo === Static checks and regression tests ===
"%PYTHON%" -m compileall -q playstore_app_audit
if errorlevel 1 exit /b 1
"%PYTHON%" -m py_compile .github\scripts\inspect_pe.py .github\scripts\validate_windows_standalone.py .github\scripts\prepare_release_legal_bundle.py .github\scripts\validate_release_legal_bundle.py
if errorlevel 1 exit /b 1
"%PYTHON%" -m pytest
if errorlevel 1 exit /b 1
"%PYTHON%" -m ruff check playstore_app_audit tests main.py .github\scripts\inspect_pe.py .github\scripts\validate_windows_standalone.py .github\scripts\prepare_release_legal_bundle.py .github\scripts\validate_release_legal_bundle.py
if errorlevel 1 exit /b 1

echo.
echo === Qt source smoke tests ===
set "QT_QPA_PLATFORM=offscreen"
"%PYTHON%" -c "from PySide6.QtWidgets import QApplication; from playstore_app_audit.ui.main_window import MainWindow; app=QApplication([]); w=MainWindow(); assert w.path_edit.isHidden(); assert w.choose_button.text()=='Choose File'; assert w.scan_button.text()=='Scan Phone'; old='Audit completed - 10 cached - 2 live'; w.status_label.setText(old); w._set_view_preset('Device'); assert w.status_label.text()==old; assert w.country_edit.text(); print('Qt source smoke test OK'); w.close()"
if errorlevel 1 exit /b 1
set "PLAYSTORE_APP_AUDIT_SMOKE_TEST=1"
"%PYTHON%" main.py
if errorlevel 1 exit /b 1
set "PLAYSTORE_APP_AUDIT_SMOKE_TEST="
set "QT_QPA_PLATFORM="

echo.
echo === Build standalone package ===
powershell -NoProfile -ExecutionPolicy Bypass -File ".github\scripts\build_windows_standalone.ps1" -PythonExe "%PYTHON%" -RepoRoot "%CD%" -OutputRoot "artifact\windows-x64-local" -ExpectedPeMachine "0x8664" -ExpectedPlatformMachine "AMD64" -PackageArch "x64" -PrivateBuild
if errorlevel 1 exit /b 1

echo.
echo Windows x64 standalone build completed successfully.
echo Output: artifact\windows-x64-local
