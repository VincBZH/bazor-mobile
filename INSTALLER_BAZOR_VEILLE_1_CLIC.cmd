@echo off
setlocal EnableExtensions
title BAZOR - installer la veille sans doublon
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Windows n'est pas accessible par py. Aucune installation.
  pause
  exit /b 2
)
py -3 "%~dp0pc-relay\bazor_boot_watch.py" --install
if errorlevel 1 (
  echo Echec de l'installation. Aucun service BAZOR n'a ete arrete.
  pause
  exit /b 2
)
exit /b 0
