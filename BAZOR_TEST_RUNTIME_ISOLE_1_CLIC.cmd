@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR - TEST RUNTIME ISOLE V24
cd /d "%~dp0"
set "ROOT=%CD%"
set "REPORTDIR=%LOCALAPPDATA%\BAZOR\Reports"
if not exist "%REPORTDIR%" mkdir "%REPORTDIR%" >nul 2>&1
set "PREFLIGHT=%REPORTDIR%\runtime_isole_preflight.txt"
set "ONECLICK=%REPORTDIR%\runtime_isole_oneclick.txt"
set "SMOKE=%REPORTDIR%\runtime_isole_smoke.txt"
set "PUBLIC=%REPORTDIR%\runtime_isole_public.txt"

echo ============================================================
echo BAZOR V24 - TEST REEL ISOLE
echo Production conservee : Core 8775 / Room 8765
echo Candidat isole       : Core 8875 / Room 8768
echo IA utilisee          : Ollama local uniquement
echo API payante          : ZERO
echo ============================================================
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
if exist "C:\AI\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe" (
  set "PYEXE=C:\AI\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe"
  set "PYARGS="
  goto python_ok
)
echo [BLOQUE] Python introuvable. Aucun changement effectue.
exit /b 2

:python_ok
echo [1/3] Verification du candidat V24 + sauvegarde locale...
"%PYEXE%" %PYARGS% "%ROOT%\pc-relay\bazor_compat_preflight.py" --stage "%ROOT%" --public-only > "%PREFLIGHT%" 2>&1
set "RC=%ERRORLEVEL%"
type "%PREFLIGHT%"
if not "%RC%"=="0" (
  echo.
  echo [BLOQUE] Le preflight refuse ce candidat. Aucun runtime isole lance.
  exit /b %RC%
)

echo.
echo [2/3] Demarrage/test gratuit du Core 8875 + Room 8768 + Ollama...
"%PYEXE%" %PYARGS% "%ROOT%\pc-relay\bazor_multiai_oneclick.py" --no-github > "%ONECLICK%" 2>&1
set "RC=%ERRORLEVEL%"
type "%ONECLICK%"
if not "%RC%"=="0" (
  echo.
  echo [BLOQUE] Le test local one-click a echoue. Production non remplacee.
  exit /b %RC%
)

echo.
echo [3/3] Controle identite + vrai dialogue Ollama + stabilite production...
"%PYEXE%" %PYARGS% "%ROOT%\pc-relay\bazor_isolated_runtime_smoke.py" --allow-local-chat > "%SMOKE%" 2>&1
set "RC=%ERRORLEVEL%"
type "%SMOKE%"

> "%PUBLIC%" echo [BAZOR-RUNTIME-ISOLATED-RESULT]
>> "%PUBLIC%" echo REQUEST_ID: RUNTIME-V24-ISOLE-20260927
>> "%PUBLIC%" type "%SMOKE%"

if "%RC%"=="0" (
  echo.
  echo [PASS] Runtime V24 isole verifie. Aucun deploiement effectue.
) else (
  echo.
  echo [BLOQUE] Runtime isole non certifie. Aucun deploiement effectue.
)

where gh >nul 2>&1
if not errorlevel 1 (
  gh auth status >nul 2>&1
  if not errorlevel 1 (
    gh issue comment 171 --repo VincBZH/bazor-mobile --body-file "%PUBLIC%" >nul 2>&1
    if not errorlevel 1 echo [GITHUB] Resultat public assaini publie sur issue #171.
  )
)

echo.
echo Rapport public : %PUBLIC%
echo API payante : ZERO
echo Production remplacee : NON
exit /b %RC%
