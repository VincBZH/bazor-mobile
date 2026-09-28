@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title BAZOR - TEST RETOUR ARRIERE SIMULE, SANS INSTALLATION
cd /d "%~dp0"
set "REPORT_DIR=%LOCALAPPDATA%\BAZOR\Reports"
if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%" >nul 2>&1
set "PUBLIC=%REPORT_DIR%\BAZOR_ROLLBACK_REHEARSAL_PUBLIC.txt"
echo ============================================================
echo BAZOR - SIMULATION D'ECHEC ET RESTAURATION EN DOSSIER TEMPORAIRE
echo Core / Room de production : jamais modifies
echo Aucun redemarrage, aucune API payante, aucun deploiement
echo ============================================================
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0pc-relay\bazor_rollback_rehearsal.py" > "%PUBLIC%" 2>nul
  set "RC=%ERRORLEVEL%"
  goto report
)
where python >nul 2>&1
if not errorlevel 1 (
  python "%~dp0pc-relay\bazor_rollback_rehearsal.py" > "%PUBLIC%" 2>nul
  set "RC=%ERRORLEVEL%"
  goto report
)
echo [BLOQUE] Python 3 introuvable. Aucun fichier modifie.
set "RC=2"
goto end

:report
type "%PUBLIC%"
echo.
where gh >nul 2>&1
if errorlevel 1 goto local_only
gh auth status >nul 2>&1
if errorlevel 1 goto local_only
rem The Python module prints ONLY the fixed-vocabulary public summary.
rem No raw logs, path, ZIP, environment or private JSON are uploaded.
gh issue comment 171 --repo VincBZH/bazor-mobile --body-file "%PUBLIC%" >nul 2>&1
if not errorlevel 1 (
  echo [GITHUB] Rapport assaini publie automatiquement sur issue 171.
  goto end
)
:local_only
echo [INFO] Rapport enregistre localement ; GitHub non disponible.
:end
echo.
if "%RC%"=="0" (
  echo [PASS] Retour arriere SIMULE sur copie temporaire uniquement.
) else (
  echo [BLOQUE] Simulation non certifiee. Installations non modifiees.
)
echo Aucun fichier prive, aucune archive et aucune cle n'ont ete publies.
pause
exit /b %RC%
