@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR CORE v3

echo ==============================================================
echo  BAZOR CORE v3 - OLLAMA + MAMMOUTH + RELAY GPT AUTOMATIQUE
echo ==============================================================
echo.
echo Ollama = local gratuit prioritaire.
echo Mammouth = relais externe avec plafond budgetaire.
echo GitHub issue #2 = canal automatique GPT ^<^> Mammouth.
echo Aucune commande shell recue depuis GitHub n'est executee.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [BLOQUE] Python introuvable sur ce PC.
  pause
  exit /b 1
)

echo [1/5] Verification de la cle Mammouth...
if not defined MAMMOUTH_API_KEY (
  for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('MAMMOUTH_API_KEY','User')"`) do set "MAMMOUTH_API_KEY=%%K"
)
if defined MAMMOUTH_API_KEY (
  echo [OK] Cle Mammouth detectee.
) else (
  echo [INFO] Cle Mammouth absente. BAZOR fonctionnera en local uniquement.
)

echo [2/5] Verification lecture PDF...
python -c "import pypdf" >nul 2>&1
if errorlevel 1 (
  echo pypdf absent - tentative d'installation locale...
  python -m pip install --user --disable-pip-version-check --quiet pypdf >nul 2>&1
  if errorlevel 1 echo [INFO] pypdf non installe : BAZOR fonctionnera sans lecture PDF.
)

echo [3/5] Verification du code BAZOR...
python -c "import py_compile,sys,tempfile,os; [py_compile.compile(p,cfile=os.path.join(tempfile.gettempdir(),'BAZOR_VALIDATE_'+str(os.getpid())+'_'+str(i)+'.pyc'),doraise=True) for i,p in enumerate(sys.argv[1:],1)]" "%~dp0mammouth_client.py" "%~dp0mammouth_github_relay.py" "%~dp0bazor_pc_relay_v3.py"
if errorlevel 1 (
  echo.
  echo [BLOQUE] Le controle Python a detecte un probleme.
  echo Rien n'a ete lance. Copie cette fenetre dans ChatGPT.
  pause
  exit /b 1
)
python "%~dp0mammouth_github_relay.py" --selftest
if errorlevel 1 (
  echo [BLOQUE] Auto-test du relay Mammouth echoue.
  pause
  exit /b 1
)
echo [OK] Code + relay valides.

echo [4/5] Demarrage du relay GPT ^<^> Mammouth...
where gh >nul 2>&1
if errorlevel 1 (
  echo [INFO] GitHub CLI absent : relay automatique non lance.
) else if not defined MAMMOUTH_API_KEY (
  echo [INFO] Cle Mammouth absente : relay automatique non lance.
) else (
  start "BAZOR MAMMOUTH RELAY" /min cmd /k python "%~dp0mammouth_github_relay.py"
  echo [OK] Relay lance. Il surveille l'issue #2 toutes les 15 secondes.
)

echo [5/5] Demarrage BAZOR Core v3...
echo Si Windows demande une autorisation reseau, coche uniquement
echo "Reseaux prives", puis Autoriser l'acces.
echo.
python "%~dp0bazor_pc_relay_v3.py"

echo.
echo BAZOR Core arrete.
pause
