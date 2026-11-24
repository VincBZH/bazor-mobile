@echo off
chcp 65001 >nul
set "APP=C:\BAZOR\PC_Cleaner\BAZOR_PC_CLEANER.py"
set "PANIC=C:\BAZOR\PC_Cleaner\BAZOR_PANIC.py"
where pythonw >nul 2>&1
if errorlevel 1 (
  where pyw >nul 2>&1
  if errorlevel 1 (
    echo Python 3 est introuvable. BAZOR Cleaner ne peut pas demarrer.
    pause
    exit /b 1
  )
  start "BAZOR PC CLEANER ULTIMATE" pyw -3 "%APP%"
  start "BAZOR PANIC" pyw -3 "%PANIC%"
) else (
  start "BAZOR PC CLEANER ULTIMATE" pythonw "%APP%"
  start "BAZOR PANIC" pythonw "%PANIC%"
)
