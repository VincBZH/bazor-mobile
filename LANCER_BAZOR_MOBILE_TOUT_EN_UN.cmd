@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR MOBILE - TOUT EN UN
cd /d "%~dp0\.."

echo ============================================================
echo   BAZOR MOBILE - CORE + OLLAMA + GITHUB + CHROME
echo ============================================================
echo.

where python >nul 2>nul || (echo [BLOQUE] Python introuvable.& pause& exit /b 1)
where gh >nul 2>nul || (echo [BLOQUE] GitHub CLI introuvable.& pause& exit /b 1)

git pull
echo.

powershell -NoProfile -Command "if(Get-NetTCPConnection -LocalPort 8775 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}"
if errorlevel 1 (
  echo [START] BAZOR Mobile Core 8775
  start "BAZOR MOBILE CORE 8775" cmd /k "cd /d ""%CD%"" && set BAZOR_MOBILE_PORT=8775 && python pc-relay\bazor_pc_relay_v3.py"
) else (
  echo [OK] Core 8775 deja actif.
)

powershell -NoProfile -Command "if(Get-NetTCPConnection -LocalPort 8776 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}"
if errorlevel 1 (
  echo [START] Interface Chrome 8776
  start "BAZOR MOBILE WEB 8776" cmd /k "cd /d ""%~dp0"" && python -m http.server 8776 --bind 0.0.0.0"
) else (
  echo [OK] Web 8776 deja actif.
)

echo [START] GitHub Watcher
start "BAZOR GITHUB WATCHER" cmd /k "cd /d ""%CD%"" && python pc-relay\bazor_github_watcher.py"

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$x=Get-NetIPAddress -AddressFamily IPv4 ^| ? {$_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown'} ^| select -First 1 -ExpandProperty IPAddress; if($x){$x}"`) do set "BAZOR_IP=%%I"

echo.
echo ============================================================
if defined BAZOR_IP (
  echo  SUR LE TELEPHONE, CHROME :
  echo  http://%BAZOR_IP%:8776/
) else (
  echo  IP locale non detectee. Lance ipconfig et utilise IPv4:8776
)
echo ============================================================
echo.
echo PC allume : interface directe via Wi-Fi.
echo PC eteint : les demandes GitHub restent en attente et seront reprises.
echo Ne ferme pas les fenetres BAZOR pendant l'utilisation.
echo.
pause
