@echo off
title KeepAwake Pro
color 0A
cls

echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║                      KeepAwake Pro                              ║
echo  ║              Sleep Prevention Utility                           ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.

REM Change to script directory
cd /d "%~dp0"

if not exist "keepawake_pro.py" (
    echo [ERROR] keepawake_pro.py not found in this folder.
    pause
    exit /b 1
)

echo [*] Verifying dependencies...
python -m pip install --user --quiet customtkinter pystray pillow pynput psutil 2>nul

echo [*] Starting KeepAwake Pro...
echo.
echo  The app will appear in your system tray.
echo  Right-click the tray icon to show or quit.
echo  Hotkeys: Ctrl+Alt+K to toggle, Ctrl+Alt+H to show/hide.
echo.

timeout /t 1 >nul

start "" pythonw keepawake_pro.py

exit
