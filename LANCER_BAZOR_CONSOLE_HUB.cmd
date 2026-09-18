@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR CONSOLE HUB - LANCEUR

set "ROOT=%USERPROFILE%\bazor-mobile"
set "HUB=%ROOT%\console-hub\bazor_console_hub.py"
set "REVIEW=%ROOT%\console-hub\bazor_hub_expert_review.py"

if not exist "%HUB%" (
  echo [BLOQUE] BAZOR Console Hub absent : %HUB%
  pause
  exit /b 1
)

if exist "%REVIEW%" (
  echo [INFO] Tests statiques + revue experte Mammouth lances en parallele...
  start "" /b python "%REVIEW%" >nul 2>&1
)

where pythonw >nul 2>nul
if errorlevel 1 (
  echo [INFO] pythonw introuvable, lancement avec python.
  start "BAZOR CONSOLE HUB" python "%HUB%" --centralize
) else (
  start "BAZOR CONSOLE HUB" pythonw "%HUB%" --centralize
)

echo [OK] BAZOR Console Hub lance.
echo Les services Core/Web/Watcher seront regroupes sans fenetres CMD visibles.
timeout /t 2 /nobreak >nul
exit /b 0
