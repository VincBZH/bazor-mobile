@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR - TABLEAU PROJETS DYNAMIQUE

set "ROOT=%USERPROFILE%\bazor-mobile"
set "APP=%ROOT%\console-hub\bazor_project_dashboard.py"
set "PY="

if not exist "%ROOT%" (
  echo [BLOQUE] Depot BAZOR introuvable : %ROOT%
  pause
  exit /b 1
)

cd /d "%ROOT%"

where git >nul 2>nul
if not errorlevel 1 (
  git pull --ff-only >nul 2>&1
)

if not exist "%APP%" (
  echo [BLOQUE] Tableau projets absent : %APP%
  echo Lance d'abord une mise a jour du depot.
  pause
  exit /b 2
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"

if defined PY (
  start "" "%PY%" "%APP%"
  exit /b 0
)

where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw "%APP%"
  exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
  start "" pyw -3 "%APP%"
  exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
  start "" python "%APP%"
  exit /b 0
)

echo [BLOQUE] Python introuvable.
pause
exit /b 3
