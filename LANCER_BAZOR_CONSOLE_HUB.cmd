@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR ONE CLICK - CLEAN START

set "ROOT=%USERPROFILE%\bazor-mobile"
set "HUB=%ROOT%\console-hub\bazor_console_hub.py"
set "CLEAN=%ROOT%\console-hub\bazor_clean_start.ps1"
set "STARTER=%ROOT%\console-hub\bazor_start_hub.ps1"

if not exist "%HUB%" (
  echo [BLOQUE] BAZOR Console Hub absent : %HUB%
  pause
  exit /b 1
)

if not exist "%STARTER%" (
  echo [BLOQUE] Lanceur Python autonome absent : %STARTER%
  pause
  exit /b 2
)

where git >nul 2>nul
if not errorlevel 1 (
  cd /d "%ROOT%"
  git pull --ff-only >nul 2>&1
)

if exist "%CLEAN%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%CLEAN%" -Root "%ROOT%" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%STARTER%" -Root "%ROOT%"
if errorlevel 1 (
  echo.
  echo [BLOQUE] Le Hub n'a pas pu demarrer. La cause est affichee ci-dessus.
  pause
  exit /b 3
)

exit /b 0
