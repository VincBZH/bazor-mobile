@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 create_desktop_launcher.py
) else (
  python create_desktop_launcher.py
)
pause
