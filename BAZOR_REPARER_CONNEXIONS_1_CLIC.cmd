@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR - Connexions IA - TEST ET REPARATION SANS RISQUE
cd /d "%~dp0"
echo =============================================================
echo BAZOR : diagnostic puis lancement local isole en un clic
echo Aucun programme BAZOR existant ne sera remplace ou arrete.
echo Test Ollama local puis UNE requete Mammouth si cle et budget OK.
echo GPT/Astra/NoTrack : pas de faux statut de connexion.
echo =============================================================
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0pc-relay\bazor_multiai_oneclick.py" --test-mammouth
  goto result
)
where python >nul 2>&1
if not errorlevel 1 (
  python "%~dp0pc-relay\bazor_multiai_oneclick.py" --test-mammouth
  goto result
)
if exist "C:\AI\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe" (
  "C:\AI\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe" "%~dp0pc-relay\bazor_multiai_oneclick.py" --test-mammouth
  goto result
)
echo [BLOQUE] Python introuvable. Aucun changement sur le PC.
pause
exit /b 2
:result
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (echo [TEST COMPLET] Ollama et Mammouth verifies.) else (echo [PARTIEL OU BLOQUE] Lire le rapport LOCALAPPDATA\BAZOR_ONECLICK.)
echo.
echo Code retour : %CODE%
pause
exit /b %CODE%
