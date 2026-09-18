@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR ONE CLICK - CLEAN START

set "ROOT=%USERPROFILE%\bazor-mobile"
set "HUB=%ROOT%\console-hub\bazor_console_hub.py"
set "REVIEW=%ROOT%\console-hub\bazor_hub_expert_review.py"
set "CLEAN=%ROOT%\console-hub\bazor_clean_start.ps1"

if not exist "%HUB%" (
  echo [BLOQUE] BAZOR Console Hub absent : %HUB%
  pause
  exit /b 1
)

where git >nul 2>nul
if not errorlevel 1 (
  cd /d "%ROOT%"
  git pull >nul 2>&1
)

if exist "%CLEAN%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%CLEAN%" -Root "%ROOT%" >nul 2>&1
)

where pythonw >nul 2>nul
if errorlevel 1 (
  set "PYGUI=python"
) else (
  set "PYGUI=pythonw"
)

if exist "%REVIEW%" (
  start "" /b %PYGUI% "%REVIEW%" >nul 2>&1
)

if /I "%PYGUI%"=="python" (
  start "BAZOR CONSOLE HUB" python "%HUB%" --centralize
) else (
  start "" pythonw "%HUB%" --centralize
)

exit /b 0
