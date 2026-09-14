@echo off
setlocal
chcp 65001 >nul
title BAZOR CORE v2

echo ==========================================================
echo  BAZOR CORE v2 - API + AUTO ECO + FICHIERS + GO AUTO
echo ==========================================================
echo.
echo Ollama reste local. GPT n'est jamais lance automatiquement.
echo Aucune commande shell n'est exposee par l'API BAZOR.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [BLOQUE] Python introuvable sur ce PC.
  pause
  exit /b 1
)

echo [1/2] Verification lecture PDF...
python -c "import pypdf" >nul 2>&1
if errorlevel 1 (
  echo pypdf absent - tentative d'installation locale...
  python -m pip install --user --disable-pip-version-check --quiet pypdf >nul 2>&1
  if errorlevel 1 echo [INFO] pypdf non installe : BAZOR fonctionnera sans lecture PDF.
)

echo [2/2] Demarrage BAZOR Core v2...
echo Si Windows demande une autorisation reseau, coche uniquement

echo "Reseaux prives", puis Autoriser l'acces.
echo.
python "%~dp0bazor_pc_relay_v2.py"

echo.
echo BAZOR Core arrete.
pause
