@echo off
setlocal
chcp 65001 >nul
title BAZOR CORE v3

echo ==============================================================
echo  BAZOR CORE v3 - OLLAMA + MAMMOUTH AUTO+ + FICHIERS + GO AUTO
echo ==============================================================
echo.
echo Ollama = local gratuit prioritaire.
echo Mammouth = relais externe avec plafond budgetaire.
echo Aucune commande shell n'est exposee par l'API BAZOR.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [BLOQUE] Python introuvable sur ce PC.
  pause
  exit /b 1
)

echo [1/4] Verification de la cle Mammouth...
if defined MAMMOUTH_API_KEY (
  echo [OK] Cle Mammouth detectee.
) else (
  echo [INFO] Cle Mammouth absente. BAZOR fonctionnera en local uniquement.
)

echo [2/4] Verification lecture PDF...
python -c "import pypdf" >nul 2>&1
if errorlevel 1 (
  echo pypdf absent - tentative d'installation locale...
  python -m pip install --user --disable-pip-version-check --quiet pypdf >nul 2>&1
  if errorlevel 1 echo [INFO] pypdf non installe : BAZOR fonctionnera sans lecture PDF.
)

echo [3/4] Verification du code BAZOR v3...
python -m py_compile "%~dp0mammouth_client.py" "%~dp0bazor_pc_relay_v3.py"
if errorlevel 1 (
  echo.
  echo [BLOQUE] Le controle Python a detecte un probleme.
  echo Rien n'a ete lance. Copie cette fenetre dans ChatGPT.
  pause
  exit /b 1
)
echo [OK] Code valide.

echo [4/4] Demarrage BAZOR Core v3...
echo Si Windows demande une autorisation reseau, coche uniquement

echo "Reseaux prives", puis Autoriser l'acces.
echo.
python "%~dp0bazor_pc_relay_v3.py"

echo.
echo BAZOR Core arrete.
pause
