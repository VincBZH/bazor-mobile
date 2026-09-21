@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR - CREER RACCOURCI PROJETS

set "ROOT=%USERPROFILE%\bazor-mobile"
set "TARGET=%ROOT%\LANCER_BAZOR_PROJETS.cmd"

if not exist "%TARGET%" (
  echo [BLOQUE] Lanceur introuvable : %TARGET%
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $s=$ws.CreateShortcut((Join-Path $desktop 'BAZOR - Projets.lnk')); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%ROOT%'; $s.Description='BAZOR - Tableau dynamique des projets'; $s.Save()"

if errorlevel 1 (
  echo [BLOQUE] Impossible de creer le raccourci.
  pause
  exit /b 2
)

echo [OK] Raccourci cree sur le Bureau : BAZOR - Projets
pause
exit /b 0
