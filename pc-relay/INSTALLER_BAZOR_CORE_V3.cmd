@echo off
setlocal EnableExtensions
chcp 65001 >nul
title INSTALLATION BAZOR CORE v3 + MAMMOUTH RELAY

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
echo  BAZOR CORE v3 + MAMMOUTH RELAY - MISE A JOUR PROPRE
echo ==============================================================
echo.
echo Dossier : %INSTALL_DIR%
echo Donnees BAZOR_DATA : conservees
echo Sauvegarde reversible : %QUAR_DIR%
echo.

echo [1/9] Arret cible et sauvegarde de l'ancienne version...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$install=[IO.Path]::GetFullPath('%INSTALL_DIR%'); $log='%LOG_FILE%'; Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -and ($_.CommandLine -like ('*'+$install+'*mammouth_github_relay.py*') -or $_.CommandLine -like ('*'+$install+'*bazor_pc_relay_v3.py*')) } | ForEach-Object { Add-Content -LiteralPath $log -Value ((Get-Date -Format o)+' | STOP | PID='+$_.ProcessId+' | mise a jour | INSTALLER_BAZOR_CORE_V3'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 1 /nobreak >nul
for %%F in (bazor_pc_relay_v3.py bazor_security.py mammouth_client.py mammouth_github_relay.py DEMARRER_BAZOR_PC_RELAY.cmd test_bazor_v3.py) do (
  if exist "%INSTALL_DIR%\%%F" (
    if not exist "%QUAR_DIR%" mkdir "%QUAR_DIR%" >nul 2>&1
    move /Y "%INSTALL_DIR%\%%F" "%QUAR_DIR%\" >nul
    echo %date% %time% ^| ARCHIVE ^| %%F ^| mise a jour ^| INSTALLER_BAZOR_CORE_V3>>"%LOG_FILE%"
  )
)

echo [2/9] Telechargement BAZOR Core + relay Mammouth...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/bazor_pc_relay_v3.py' -OutFile '%INSTALL_DIR%\bazor_pc_relay_v3.py'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/bazor_security.py' -OutFile '%INSTALL_DIR%\bazor_security.py'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/mammouth_client.py' -OutFile '%INSTALL_DIR%\mammouth_client.py'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/mammouth_github_relay.py' -OutFile '%INSTALL_DIR%\mammouth_github_relay.py'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/DEMARRER_BAZOR_PC_RELAY.cmd' -OutFile '%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd'; Invoke-WebRequest -UseBasicParsing '%BASE_URL%/test_bazor_v3.py' -OutFile '%INSTALL_DIR%\test_bazor_v3.py'"
if errorlevel 1 (
  echo [BLOQUE] Telechargement impossible.
  echo Ancienne version conservee dans : %QUAR_DIR%
  pause
  exit /b 1
)

echo [3/9] Verification Python et cle Mammouth...
where python >nul 2>&1
if errorlevel 1 (
  echo [BLOQUE] Python introuvable.
  pause
  exit /b 1
)
if not defined MAMMOUTH_API_KEY (
  for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('MAMMOUTH_API_KEY','User')"`) do set "MAMMOUTH_API_KEY=%%K"
)
if defined MAMMOUTH_API_KEY (
  echo [OK] Cle Mammouth detectee depuis Windows.
) else (
  echo [INFO] Cle Mammouth non detectee. Installation possible, relay inactif tant qu'elle manque.
)

echo [4/9] Verification GitHub CLI...
where gh >nul 2>&1
if errorlevel 1 (
  echo [INFO] GitHub CLI introuvable : Core fonctionnera, relay GPT/Mammouth non lance.
) else (
  gh auth status >nul 2>&1
  if errorlevel 1 (
    echo [INFO] GitHub CLI present mais non authentifie.
  ) else (
    echo [OK] GitHub CLI authentifie.
  )
)

echo [5/9] Verification du code...
python -m py_compile "%INSTALL_DIR%\bazor_security.py" "%INSTALL_DIR%\mammouth_client.py" "%INSTALL_DIR%\mammouth_github_relay.py" "%INSTALL_DIR%\bazor_pc_relay_v3.py" "%INSTALL_DIR%\test_bazor_v3.py"
if errorlevel 1 (
  echo [BLOQUE] Verification Python echouee.
  echo Ancienne version conservee dans : %QUAR_DIR%
  pause
  exit /b 1
)

echo [6/9] Auto-test relay Mammouth...
pushd "%INSTALL_DIR%"
python mammouth_github_relay.py --selftest
set "RELAY_TEST=%ERRORLEVEL%"
popd
if not "%RELAY_TEST%"=="0" (
  echo [BLOQUE] Self-test relay echoue.
  pause
  exit /b 1
)
echo [OK] Relay GPT ^<^> Mammouth valide sans appel API.

echo [7/9] Lecture PDF + test BAZOR sans depense...
python -c "import pypdf" >nul 2>&1
if errorlevel 1 python -m pip install --user --disable-pip-version-check --quiet pypdf >nul 2>&1
pushd "%INSTALL_DIR%"
python test_bazor_v3.py
set "CORE_TEST=%ERRORLEVEL%"
popd
if not "%CORE_TEST%"=="0" (
  echo [BLOQUE] Le test BAZOR v3 a echoue.
  pause
  exit /b 1
)

echo [8/9] Creation du raccourci Bureau...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\BAZOR CORE.lnk'); $s.TargetPath='%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.Save()" >nul 2>&1

echo [9/9] Verification finale...
if defined MAMMOUTH_API_KEY (
  echo [OK] Mammouth configure.
) else (
  echo [JAUNE] Mammouth non configure : cle absente.
)
where gh >nul 2>&1
if not errorlevel 1 (
  gh auth status >nul 2>&1
  if not errorlevel 1 echo [OK] Canal GitHub disponible pour issue #2.
)

echo.
echo ==============================================================
echo  TOUT EST OK - BAZOR CORE + RELAY INSTALLES
echo ==============================================================
echo Routage lourd :
echo   CODE     - Claude Sonnet 5
echo   ANALYSE  - GPT-5.6 Terra
echo   COMPLEXE - GPT-5.6 Sol
echo.
echo Le relay surveille : VincBZH/projetWII-ai-relay issue #2
echo Il execute uniquement des appels IA et GitHub prevus.
echo Aucun commentaire GitHub n'est execute comme commande systeme.
echo Budget Mammouth BAZOR : variable BAZOR_MAMMOUTH_BUDGET_USD.
echo Valeur par defaut actuelle : 4 dollars / mois.
echo.
echo Demarrage de BAZOR CORE...
start "" "%INSTALL_DIR%\DEMARRER_BAZOR_PC_RELAY.cmd"
echo.
echo Tu peux fermer cette fenetre.
pause
