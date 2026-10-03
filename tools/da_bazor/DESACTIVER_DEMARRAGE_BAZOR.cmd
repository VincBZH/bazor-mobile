@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 startup_disable.py disable
) else (
  python startup_disable.py disable
)
echo.
echo Conservez le dossier local de restauration. Aucun redemarrage automatique.
pause
