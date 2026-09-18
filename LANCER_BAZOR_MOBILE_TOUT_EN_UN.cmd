@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR MOBILE - TOUT EN UN
set "ROOT=%USERPROFILE%\bazor-mobile"
cd /d "%ROOT%"

echo ============================================================
echo   BAZOR MOBILE - CORE + OLLAMA + GITHUB + CHROME
echo ============================================================
echo Dossier : %CD%
echo.

if not exist "%ROOT%\pc-relay\bazor_github_watcher.py" (
 echo [BLOQUE] Watcher absent : %ROOT%\pc-relay\bazor_github_watcher.py
 pause
 exit /b 1
)

where python >nul 2>nul || (echo [BLOQUE] Python introuvable.& pause& exit /b 1)
where gh >nul 2>nul || (echo [BLOQUE] GitHub CLI introuvable.& pause& exit /b 1)

git pull

echo [INFO] Verification acces reseau local BAZOR...
netsh advfirewall firewall show rule name="BAZOR Mobile Core 8775" >nul 2>nul
if errorlevel 1 (
  netsh advfirewall firewall add rule name="BAZOR Mobile Core 8775" dir=in action=allow protocol=TCP localport=8775 profile=private remoteip=localsubnet >nul 2>nul
  if errorlevel 1 (
    echo [BLOQUE] Impossible d'ouvrir 8775 au reseau local. Lance ce fichier en Administrateur.
  ) else (
    echo [OK] Pare-feu : Core 8775 autorise uniquement sur le reseau prive/local.
  )
) else (
  echo [OK] Pare-feu Core 8775 deja configure.
)

netsh advfirewall firewall show rule name="BAZOR Mobile Web 8776" >nul 2>nul
if errorlevel 1 (
  netsh advfirewall firewall add rule name="BAZOR Mobile Web 8776" dir=in action=allow protocol=TCP localport=8776 profile=private remoteip=localsubnet >nul 2>nul
  if not errorlevel 1 echo [OK] Pare-feu : Web 8776 autorise uniquement sur le reseau prive/local.
)

powershell -NoProfile -Command "if(Get-NetTCPConnection -LocalPort 8775 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}"
if errorlevel 1 (
 start "BAZOR MOBILE CORE 8775" cmd /k "cd /d %ROOT% && set BAZOR_MOBILE_PORT=8775 && python pc-relay\bazor_pc_relay_v3.py"
) else echo [OK] Core 8775 deja actif.

powershell -NoProfile -Command "if(Get-NetTCPConnection -LocalPort 8776 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}"
if errorlevel 1 (
 start "BAZOR MOBILE WEB 8776" cmd /k "cd /d %ROOT% && python -m http.server 8776 --bind 0.0.0.0"
) else echo [OK] Web 8776 deja actif.

start "BAZOR GITHUB WATCHER" cmd /k "cd /d %ROOT% && python pc-relay\bazor_github_watcher.py"

set "BAZOR_IP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4.*:"') do if not defined BAZOR_IP for /f "tokens=* delims= " %%B in ("%%A") do set "BAZOR_IP=%%B"

echo.
echo ============================================================
echo  SUR LE TELEPHONE, CHROME :
if defined BAZOR_IP (echo  http://%BAZOR_IP%:8776/) else (echo  [BLOQUE] IPv4 non detectee.)
echo ============================================================
echo.
echo Laisse les fenetres BAZOR ouvertes.
pause
