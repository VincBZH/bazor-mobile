@echo off
setlocal
chcp 65001 >nul
title BAZOR PC RELAY

echo ==========================================================
echo  BAZOR PC RELAY
echo ==========================================================
echo.
echo Detection securisee du PC sur le reseau local.
echo Ollama n'est PAS expose.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [BLOQUE] Python introuvable sur ce PC.
  pause
  exit /b 1
)

echo Demarrage...
echo Si Windows demande une autorisation reseau, coche uniquement
echo "Reseaux prives", puis Autoriser l'acces.
echo.
python "%~dp0bazor_pc_relay.py"

echo.
echo Relais arrete.
pause
