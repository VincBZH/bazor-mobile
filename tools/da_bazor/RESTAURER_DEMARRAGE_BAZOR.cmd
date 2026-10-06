@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 startup_disable.py restore
) else (
  python startup_disable.py restore
)
pause
