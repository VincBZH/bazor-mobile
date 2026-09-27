@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR - SIMULATION RETOUR ARRIERE (SANS INSTALLATION)
cd /d "%~dp0"
set "ROOT=%CD%"
set "REPORTDIR=%LOCALAPPDATA%\BAZOR\Reports"
if not exist "%REPORTDIR%" mkdir "%REPORTDIR%" >nul 2>&1
set "PUBLIC=%REPORTDIR%\rollback_simulation_public.txt"

echo ==========================================================
echo BAZOR - SIMULATION RESTAURATION EN UN CLIC
echo Utilise UNIQUEMENT une copie temporaire de la sauvegarde.
echo Core/Room/Ollama existants : AUCUNE MODIFICATION
echo Appels payants : ZERO. Deploiement : AUCUN.
echo ==========================================================
echo.

where py >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=py"
    set "PYARGS=-3"
    goto python_ok
)
where python >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=python"
    set "PYARGS="
    goto python_ok
)
echo [BLOQUE] Python introuvable.
pause
exit /b 2

:python_ok
"%PYEXE%" %PYARGS% "%ROOT%\pc-relay\bazor_rollback_simulation.py" > "%PUBLIC%" 2>&1
set "RC=%ERRORLEVEL%"
type "%PUBLIC%"
echo.
if not "%RC%"=="0" (
    echo [BLOQUE] Simulation echouee ou refus de securite. Production intacte.
    pause
    exit /b %RC%
)
echo [PASS] Restauration simulee uniquement. AUCUNE installation autorisee par ce test.

where gh >nul 2>&1
if not errorlevel 1 (
    gh auth status >nul 2>&1
    if not errorlevel 1 (
        gh issue comment 171 --repo VincBZH/bazor-mobile --body-file "%PUBLIC%" >nul 2>&1
        if not errorlevel 1 echo [GITHUB] Resume public assaini publie sur issue #171.
    )
)
echo.
echo Rapport : %PUBLIC%
echo IMPORTANT : installation reelle et retour arriere de production NON testes.
pause
exit /b 0
