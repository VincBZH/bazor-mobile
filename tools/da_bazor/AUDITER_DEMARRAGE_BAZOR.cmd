@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 startup_audit.py
) else (
  python startup_audit.py
)
echo.
echo Audit termine. Aucun demarrage modifie. Transmettez RAPPORT_DA_BAZOR_DEMARRAGE.txt.
pause
