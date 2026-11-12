@echo off
setlocal EnableExtensions
if not exist "%LOCALAPPDATA%\BAZOR\Veille\bazor_boot_watch.pyw" (
  echo Veille BAZOR non installee a l'emplacement attendu.
  pause
  exit /b 2
)
py -3 "%LOCALAPPDATA%\BAZOR\Veille\bazor_boot_watch.pyw" --uninstall
if errorlevel 1 pause
