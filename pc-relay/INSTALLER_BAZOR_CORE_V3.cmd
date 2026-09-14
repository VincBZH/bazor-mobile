@echo off
setlocal EnableExtensions
chcp 65001 >nul
title INSTALLATION BAZOR CORE v3

set "INSTALL_DIR=%LOCALAPPDATA%\BAZOR\Core"
set "QUAR_ROOT=%LOCALAPPDATA%\BazorDiskCleaner\Quarantine\BAZOR_CORE"
set "LOG_DIR=%LOCALAPPDATA%\BazorDiskCleaner\Logs"
set "LOG_FILE=%LOG_DIR%\BAZOR_CORE_INSTALL.log"
set "BASE_URL=https://raw.githubusercontent.com/VincBZH/bazor-mobile/main/pc-relay"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "QUAR_DIR=%QUAR_ROOT%\%STAMP%"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%" >nul 2>&1

echo ==============================================================
echo  BAZOR CORE v3 - INSTALLATION / MISE A JOUR PROPRE
echo ==============================================================
echo.
echo Dossier : %INSTALL_DIR%
echo Donnees : conservees dans BAZOR_DATA
echo.

echo [1/7] Sauvegarde de l'ancienne version...
if exist "%INSTALL_DIR%\bazor_pc_relay_v3.py" (
  mkdir "%QUAR_DIR%" >nul 2>&1
  move /Y "%INSTALL_DIR%\bazor_pc_relay_v3.py" "%QUAR_DIR%\" >nul
  echo %date% %time% ^| ARCHIVE ^| bazor_pc_relay_v3.py ^| mise a jour ^| INSTALLER_BAZOR_CORE_V3>>"%LOG_FILE%"
)
if exist "%INSTALL_DIR%\mammouth_client.py" (
  if not exist "%QUAR_DIR%" mkdir "%QUAR_DIR%" >nul 2>&1
  move /Y "%INSTALL_DIR%\mammouth_client.py" "%QUAR_DIR%\" >nul
  echo %date% %time% ^| ARCHIVE ^| mammouth_client.py ^| mise a jour ^| INSTALLER_BAZOR_CORE_V3>>"%LOG_FILE%"
)
if exist "%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd" (
  if not exist "%QUAR_DIR%" mkdir "%QUAR_DIR%" >nul 2>&1
  move /Y "%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd" "%QUAR_DIR%\" >nul
  echo %date% %time% ^| ARCHIVE ^| DEMARRER_BAZOR_PC_RELAY.cmd ^| mise a jour ^| INSTALLER_BAZOR_CORE_V3>>"%LOG_FILE%"
)

echo [2/7] Telechargement BAZOR Core v3...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/bazor_pc_relay_v3.py' -OutFile '%INSTALL_DIR%\bazor_pc_relay_v3.py'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/mammouth_client.py' -OutFile '%INSTALL_DIR%\mammouth_client.py'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/DEMARRER_BAZOR_PC_RELAY.cmd' -OutFile '%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd'"
if errorlevel 1 (
  echo [BLOQUE] Telechargement impossible.
  echo Verifie Internet puis relance cet installateur.
  pause
  exit /b 1
)

echo [3/7] Verification Python...
where python >nul 2>&1
if errorlevel 1 (
  echo [BLOQUE] Python introuvable.
  pause
  exit /b 1
)

echo [4/7] Verification du code...
python -m py_compile "%INSTALL_DIR%\mammouth_client.py" "%INSTALL_DIR%\bazor_pc_relay_v3.py"
if errorlevel 1 (
  echo [BLOQUE] Verification Python echouee.
  echo Ancienne version conservee dans : %QUAR_DIR%
  pause
  exit /b 1
)

echo [5/7] Lecture PDF...
python -c "import pypdf" >nul 2>&1
if errorlevel 1 python -m pip install --user --disable-pip-version-check --quiet pypdf >nul 2>&1

echo [6/7] Creation du raccourci Bureau...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\BAZOR CORE.lnk'); $s.TargetPath='%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.Save()" >nul 2>&1

echo [7/7] Verification Mammouth...
if defined MAMMOUTH_API_KEY (
  echo [OK] Cle Mammouth detectee.
) else (
  echo [INFO] Cle Mammouth non detectee dans cette session Windows.
  echo Ferme et relance cet installateur si tu viens juste de creer la cle.
)

echo.
echo ==============================================================
echo  TOUT EST OK - BAZOR CORE v3 EST INSTALLE
echo ==============================================================
echo Raccourci cree sur le Bureau : BAZOR CORE
echo Budget Mammouth BAZOR par defaut : 4 dollars / mois.
echo Les donnees BAZOR_DATA ne sont jamais supprimees par cet installateur.
echo.
echo Demarrage de BAZOR CORE...
start "" "%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd"
echo.
echo Tu peux fermer cette fenetre.
pause
