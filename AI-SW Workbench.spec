@echo off
setlocal
cd /d %~dp0

set "PYINSTALLER=pyinstaller"
if exist ".venv\Scripts\pyinstaller.exe" (
  set "PYINSTALLER=.venv\Scripts\pyinstaller.exe"
)

set "ICON_ARGS="
if exist "ui_desktop\resources\app_icon.ico" (
  set "ICON_ARGS=--icon ui_desktop\resources\app_icon.ico"
) else (
  echo Icon not found: ui_desktop\resources\app_icon.ico
  echo Building with default Windows application icon.
)

"%PYINSTALLER%" ^
  --name "AI-SW Workbench" ^
  --windowed ^
  --paths src ^
  --collect-submodules cad_dsl ^
  --collect-submodules policy ^
  --collect-submodules solidworks_api ^
  --hidden-import win32com ^
  --hidden-import win32com.client ^
  --hidden-import pythoncom ^
  --hidden-import pywintypes ^
  --hidden-import win32api ^
  --collect-all PySide6 ^
  --collect-all shiboken6 ^
  %ICON_ARGS% ^
  --add-data "ui_desktop\styles\theme.qss;ui_desktop\styles" ^
  --add-data "ui_desktop\resources\app_icon.ico;ui_desktop\resources" ^
  --add-data "ui_desktop\resources\app_icon.png;ui_desktop\resources" ^
  --add-data "resources\materials\material_catalog.json;resources\materials" ^
  --clean ^
  --noconfirm ^
  ui_desktop\main.py

if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo Build finished.
echo Output: dist\AI-SW Workbench\AI-SW Workbench.exe
pause

@echo off
setlocal
cd /d %~dp0

set "PYINSTALLER=pyinstaller"
if exist ".venv\Scripts\pyinstaller.exe" (
  set "PYINSTALLER=.venv\Scripts\pyinstaller.exe"
)

set "ICON_ARGS="
if exist "ui_desktop\resources\app_icon.ico" (
  set "ICON_ARGS=--icon ui_desktop\resources\app_icon.ico"
) else (
  echo Icon not found: ui_desktop\resources\app_icon.ico
  echo Building with default Windows application icon.
)

"%PYINSTALLER%" ^
  --name "AI-SW Workbench" ^
  --windowed ^
  --paths src ^
  --collect-submodules cad_dsl ^
  --collect-submodules policy ^
  --collect-submodules solidworks_api ^
  --hidden-import win32com ^
  --hidden-import win32com.client ^
  --hidden-import pythoncom ^
  --hidden-import pywintypes ^
  --hidden-import win32api ^
  --collect-all PySide6 ^
  --collect-all shiboken6 ^
  %ICON_ARGS% ^
  --add-data "ui_desktop\styles\theme.qss;ui_desktop\styles" ^
  --add-data "ui_desktop\resources\app_icon.ico;ui_desktop\resources" ^
  --add-data "ui_desktop\resources\app_icon.png;ui_desktop\resources" ^
  --add-data "resources\materials\material_catalog.json;resources\materials" ^
  --clean ^
  --noconfirm ^
  ui_desktop\main.py

if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo Build finished.
echo Output: dist\AI-SW Workbench\AI-SW Workbench.exe
pause

