@echo off
setlocal EnableExtensions
title BAZOR ULTIMATE V0 - Diagnostic
cd /d "%~dp0"

echo =====================================================
echo  BAZOR ULTIMATE V0 - DIAGNOSTIC LOCAL
echo  Ne demarre PAS Core, AI Room, Ollama ou Studio.
echo  Ne ferme aucun service et ne lance aucune reparation.
echo =====================================================
echo.

if not exist "console-hub\bazor_ultimate_dashboard.py" (
  echo [ERREUR] Fichier du tableau de bord absent.
  echo Decompresse le ZIP entier puis lance ce CMD depuis sa racine.
  pause
  exit /b 2
)
if not exist "console-hub\bazor_diagnostics.py" (
  echo [ERREUR] Fichier bazor_diagnostics.py absent.
  pause
  exit /b 2
)
if not exist "console-hub\bazor_console_hub.py" (
  echo [ERREUR] Le Hub existant est absent.
  pause
  exit /b 2
)

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import tkinter" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import tkinter" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)
if not defined PYTHON_CMD (
  echo [ERREUR] Python 3 avec Tkinter introuvable.
  echo Aucune installation automatique n'est effectuee.
  pause
  exit /b 3
)

%PYTHON_CMD% -c "import socket; s=socket.socket(); s.settimeout(1); occ=s.connect_ex(('127.0.0.1',8790))==0; s.close(); raise SystemExit(1 if occ else 0)"
if errorlevel 1 (
  echo [STOP] Le port 8790 est deja utilise.
  echo Une autre interface Hub ou Router est peut-etre ouverte.
  echo Ne ferme pas Core, AI Room ou Ollama. Verifie seulement l'interface deja ouverte.
  pause
  exit /b 4
)

echo [OK] Python et Tkinter disponibles. Port 8790 libre.
echo [INFO] Ouverture d'une seule interface BAZOR ULTIMATE V0...
echo [INFO] Cette fenetre CMD reste ouverte jusqu'a la fermeture du Hub.
echo.
%PYTHON_CMD% -u "console-hub\bazor_ultimate_dashboard.py"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo [ERREUR] La fenetre s'est terminee avec le code %RESULT%.
  echo Copie le message d'erreur pour le diagnostic.
  pause
)
exit /b %RESULT%
