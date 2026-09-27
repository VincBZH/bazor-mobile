@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title BAZOR - TEST RETOUR ARRIERE SIMULE, SANS INSTALLATION
cd /d "%~dp0"
echo ============================================================
echo BAZOR - SIMULATION D'ECHEC ET RESTAURATION EN DOSSIER TEMPORAIRE
echo Core / Room de production : jamais modifies
echo Aucun redemarrage, aucune API payante, aucun deploiement
echo ============================================================
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0pc-relay\bazor_rollback_rehearsal.py"
  set "RC=%ERRORLEVEL%"
  goto end
)
where python >nul 2>&1
if not errorlevel 1 (
  python "%~dp0pc-relay\bazor_rollback_rehearsal.py"
  set "RC=%ERRORLEVEL%"
  goto end
)
echo [BLOQUE] Python 3 introuvable. Aucun fichier modifie.
set "RC=2"
:end
echo.
if "%RC%"=="0" (
  echo [PASS] Retour arriere SIMULE sur copie temporaire uniquement.
) else (
  echo [BLOQUE] Simulation non certifiee. Installations non modifiees.
)
echo Le rapport contient uniquement des etats publics.
echo Merci de ne jamais partager l'archive de sauvegarde.
pause
exit /b %RC%
