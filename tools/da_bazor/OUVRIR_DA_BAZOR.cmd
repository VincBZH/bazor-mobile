@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 da_bazor.py window
) else (
  python da_bazor.py window
)
if errorlevel 1 pause
