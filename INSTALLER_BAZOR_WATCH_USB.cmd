@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BAZOR WATCH - INSTALLATION USB
chcp 65001 >nul

set "ROOT=%~dp0"
set "APK=%ROOT%BAZOR-Watch.apk"
set "LOGDIR=%LOCALAPPDATA%\BAZOR\Watch"
set "LOG=%LOGDIR%\install_usb.log"
set "DEVFILE=%TEMP%\bazor_adb_devices.txt"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1

echo ============================================================
echo   BAZOR WATCH - INSTALLATION USB
echo ============================================================
echo.
echo [%date% %time%] START >> "%LOG%"

if not exist "%APK%" (
  echo [ERREUR] BAZOR-Watch.apk est introuvable a cote de ce fichier.
  echo [%date% %time%] APK_MISSING >> "%LOG%"
  goto :error
)

call :find_adb
if not defined ADB (
  echo [INFO] ADB introuvable. Installation officielle Google Platform Tools...
  set "TOOLS=%LOCALAPPDATA%\BAZOR\Android"
  if not exist "!TOOLS!" mkdir "!TOOLS!" >nul 2>&1
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop'; $root='%LOCALAPPDATA%\BAZOR\Android'; $zip=Join-Path $root 'platform-tools.zip'; Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile $zip; Expand-Archive -Force $zip $root; Remove-Item -Force $zip"
  call :find_adb
)

if not defined ADB (
  echo [ERREUR] Impossible de trouver ou installer ADB.
  echo [%date% %time%] ADB_MISSING >> "%LOG%"
  goto :error
)

echo [OK] ADB : "%ADB%"
echo [%date% %time%] ADB=%ADB% >> "%LOG%"

"%ADB%" start-server >> "%LOG%" 2>&1
call :probe_device

if not defined SERIAL (
  echo [INFO] Telephone non pret.
  echo [INFO] Debogage USB : active. Puis accepte la fenetre RSA sur le telephone si elle apparait.
  echo [INFO] Je relance ADB et j'attends jusqu'a 60 secondes...
  "%ADB%" reconnect >> "%LOG%" 2>&1
  for /L %%N in (1,1,30) do (
    timeout /t 2 /nobreak >nul
    call :probe_device
    if defined SERIAL goto :device_ok
  )
)

:device_ok
if not defined SERIAL (
  echo.
  echo [ERREUR] Aucun telephone ADB autorise.
  echo.
  echo Etat ADB :
  type "%DEVFILE%"
  echo.
  findstr /I "unauthorized" "%DEVFILE%" >nul 2>&1
  if not errorlevel 1 (
    echo [ACTION] Regarde l'ecran du telephone et accepte "Toujours autoriser depuis cet ordinateur".
  ) else (
    echo [ACTION] Sur le telephone : Options developpeur ^> Debogage USB = active.
    echo [ACTION] Puis debranche/rebranche le cable USB une fois.
  )
  echo [%date% %time%] DEVICE_NOT_READY >> "%LOG%"
  type "%DEVFILE%" >> "%LOG%"
  goto :error
)

echo [OK] Telephone detecte : %SERIAL%
echo [%date% %time%] DEVICE=%SERIAL% >> "%LOG%"

echo [1/3] Installation de BAZOR Watch sans toucher a BAZOR Tool...
"%ADB%" -s "%SERIAL%" install -r "%APK%" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [ERREUR] Installation APK impossible.
  goto :error
)

echo [2/3] Verification du package...
"%ADB%" -s "%SERIAL%" shell pm list packages > "%TEMP%\bazor_packages.txt" 2>&1
findstr /I /C:"package:com.bazor.watch" "%TEMP%\bazor_packages.txt" >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] Package com.bazor.watch non trouve apres installation.
  goto :error
)

echo [3/3] Ouverture de BAZOR Watch...
"%ADB%" -s "%SERIAL%" shell am force-stop com.bazor.watch >> "%LOG%" 2>&1
"%ADB%" -s "%SERIAL%" shell monkey -p com.bazor.watch -c android.intent.category.LAUNCHER 1 >> "%LOG%" 2>&1

echo.
echo ============================================================
echo   TOUT EST OK
echo   BAZOR Watch est installe comme application SEPAREE.
echo   BAZOR Tool n'a pas ete remplace.
echo ============================================================
echo [%date% %time%] SUCCESS >> "%LOG%"
del "%DEVFILE%" >nul 2>&1
del "%TEMP%\bazor_packages.txt" >nul 2>&1
timeout /t 6 /nobreak >nul
exit /b 0

:probe_device
set "SERIAL="
"%ADB%" devices > "%DEVFILE%" 2>&1
for /f "usebackq tokens=1,2" %%A in ("%DEVFILE%") do (
  if "%%B"=="device" if not defined SERIAL set "SERIAL=%%A"
)
exit /b 0

:find_adb
set "ADB="
for /f "delims=" %%A in ('where adb.exe 2^>nul') do if not defined ADB set "ADB=%%A"
if not defined ADB if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not defined ADB if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
if not defined ADB if defined ANDROID_SDK_ROOT if exist "%ANDROID_SDK_ROOT%\platform-tools\adb.exe" set "ADB=%ANDROID_SDK_ROOT%\platform-tools\adb.exe"
if not defined ADB if exist "%LOCALAPPDATA%\BAZOR\Android\platform-tools\adb.exe" set "ADB=%LOCALAPPDATA%\BAZOR\Android\platform-tools\adb.exe"
exit /b 0

:error
echo.
echo ============================================================
echo   BLOCAGE - LA FENETRE RESTE OUVERTE
echo ============================================================
echo Journal : "%LOG%"
echo Envoie-moi ce qui est affiche ici ; je corrigerai la suite.
pause
exit /b 1
