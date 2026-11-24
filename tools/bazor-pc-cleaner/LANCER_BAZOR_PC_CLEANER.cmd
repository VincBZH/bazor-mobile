@echo off
chcp 65001 >nul
set "CLEANER=%~dp0BAZOR_PC_CLEANER.py"
set "PANIC=%~dp0BAZOR_PANIC.py"
where pythonw >nul 2>&1
if errorlevel 1 (
  where pyw >nul 2>&1
  if errorlevel 1 (
    echo Python 3 est introuvable. Le Cleaner n'a pas demarre.
    pause
    exit /b 1
  )
  start "BAZOR PC CLEANER ULTIMATE" pyw -3 "%CLEANER%"
  start "BAZOR PANIC" pyw -3 "%PANIC%"
) else (
  start "BAZOR PC CLEANER ULTIMATE" pythonw "%CLEANER%"
  start "BAZOR PANIC" pythonw "%PANIC%"
)
