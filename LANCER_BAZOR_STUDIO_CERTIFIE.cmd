@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title BAZOR AI SIMPLE STUDIO CERTIFIE

set "ROOT=%USERPROFILE%\bazor-mobile"
set "SCRIPT=%ROOT%\console-hub\bazor_studio_certified_launcher.py"
set "PYTHON="

echo ============================================================
echo   BAZOR AI SIMPLE STUDIO - LANCEMENT CERTIFIE
echo ============================================================
echo.

if not exist "%SCRIPT%" (
  echo [BLOQUE] Script absent:
  echo %SCRIPT%
  echo.
  if not "%BAZOR_STUDIO_NO_PAUSE%"=="1" pause
  exit /b 2
)

if exist "%ROOT%\RELANCER_WATCHER_STUDIO.cmd" (
  echo [STUDIO] Verification du watcher BAZOR...
  call "%ROOT%\RELANCER_WATCHER_STUDIO.cmd"
  if errorlevel 1 echo [INFO] Watcher non confirme, lancement Studio quand meme.
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

if defined PYTHON goto :RUNPY

where py >nul 2>nul
if not errorlevel 1 (
  echo Python: py -3
  py -3 "%SCRIPT%"
  set "RC=!ERRORLEVEL!"
  goto :AFTER
)

where python >nul 2>nul
if not errorlevel 1 (
  echo Python: python
  python "%SCRIPT%"
  set "RC=!ERRORLEVEL!"
  goto :AFTER
)

echo [BLOQUE] Python introuvable.
set "RC=11"
goto :AFTER

:RUNPY
echo Python: %PYTHON%
"%PYTHON%" "%SCRIPT%"
set "RC=!ERRORLEVEL!"

:AFTER
echo.
if "!RC!"=="0" (
  echo [OK] STUDIO CERTIFIE.
  start "" "http://127.0.0.1:8191/"
  echo [OK] Ouverture navigateur : http://127.0.0.1:8191/
) else (
  echo [BLOQUE] Le Studio n'a pas passe la certification. Code !RC!.
)

echo.
if not "%BAZOR_STUDIO_NO_PAUSE%"=="1" (
  echo Cette fenetre reste ouverte pour le diagnostic.
  pause
)
exit /b !RC!
