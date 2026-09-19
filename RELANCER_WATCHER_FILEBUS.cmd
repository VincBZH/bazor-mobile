@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title BAZOR - RELANCE WATCHER FILEBUS

set "ROOT=%USERPROFILE%\bazor-mobile"
set "WATCHER=%ROOT%\pc-relay\bazor_github_watcher.py"
set "LOG=%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS\watcher.log"

if not exist "%ROOT%\.git" (
  echo [BLOQUE] Depot BAZOR absent : %ROOT%
  pause
  exit /b 2
)

cd /d "%ROOT%"

echo [1/5] Mise a jour GitHub...
git fetch origin main
if errorlevel 1 (
  echo [BLOQUE] git fetch a echoue.
  pause
  exit /b 3
)
git pull --ff-only
if errorlevel 1 (
  echo [BLOQUE] git pull --ff-only a echoue. Aucun fichier local n'a ete ecrase.
  pause
  exit /b 4
)

echo [2/5] Verification syntaxe watcher...
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m py_compile "%WATCHER%"
  if errorlevel 1 (
    echo [BLOQUE] Syntaxe watcher invalide. Ancien watcher laisse intact.
    pause
    exit /b 5
  )
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [BLOQUE] Python introuvable.
    pause
    exit /b 6
  )
  python -m py_compile "%WATCHER%"
  if errorlevel 1 (
    echo [BLOQUE] Syntaxe watcher invalide. Ancien watcher laisse intact.
    pause
    exit /b 7
  )
  set "PY=python"
)

echo [3/5] Fermeture de l'ancien watcher uniquement...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'bazor_github_watcher\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

%SystemRoot%\System32\timeout.exe /t 1 /nobreak >nul

echo [4/5] Demarrage watcher corrige...
if not exist "%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS" mkdir "%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=(Get-Command pythonw.exe -ErrorAction SilentlyContinue); if($p){Start-Process -FilePath $p.Source -ArgumentList '"%WATCHER%"' -WorkingDirectory '%ROOT%' -WindowStyle Hidden} else {Start-Process -FilePath 'python.exe' -ArgumentList '"%WATCHER%"' -WorkingDirectory '%ROOT%' -WindowStyle Hidden}" 

%SystemRoot%\System32\timeout.exe /t 4 /nobreak >nul

echo [5/5] Controle processus...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'bazor_github_watcher\.py' }; if($p){exit 0}else{exit 1}"
if errorlevel 1 (
  echo [BLOQUE] Le watcher n'est pas reste actif.
  echo Consulte : %LOG%
  pause
  exit /b 8
)

for /f %%H in ('git rev-parse --short HEAD') do set "HEADSHA=%%H"

where gh >nul 2>nul
if not errorlevel 1 (
  set "REPORT=%TEMP%\bazor_filebus_report_%RANDOM%.txt"
  >"!REPORT!" echo [BAZOR_VERSION_REPORT]
  >>"!REPORT!" echo project: BAZOR FileBus
  >>"!REPORT!" echo status: WATCHER_RESTARTED
  >>"!REPORT!" echo commit: %HEADSHA%
  >>"!REPORT!" echo runtime: watcher_process_alive
  >>"!REPORT!" echo next: traitement automatique FileBus et test strict Mammouth #6
  >>"!REPORT!" echo note: FileBus non VERIFIE tant que les nonces ne sont pas publies.
  gh issue comment 2 --repo VincBZH/projetWII-ai-relay --body-file "!REPORT!" >nul 2>&1
  del /q "!REPORT!" >nul 2>&1
)

echo.
echo [OK] Watcher relance sur commit %HEADSHA%.
echo [OK] Il doit maintenant traiter FileBus et le test Mammouth #6 automatiquement.
echo [INFO] Ne ferme rien d'autre : Core/Studio/ComfyUI n'ont pas ete touches.
echo.
%SystemRoot%\System32\timeout.exe /t 8 /nobreak >nul
exit /b 0
