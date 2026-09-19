@echo off
setlocal
title BAZOR AI ROOM V3 - ONESHOT RECOVERY
cd /d "%~dp0"
echo ============================================================
echo  BAZOR AI ROOM V3 BETA - ONESHOT RECOVERY
echo ============================================================
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0pc-relay\bazor_room_v3_oneshot_recovery.py"
) else (
  python "%~dp0pc-relay\bazor_room_v3_oneshot_recovery.py"
)
set RC=%errorlevel%
echo.
if "%RC%"=="0" (
  echo [OK] V3 BETA PRETE - le panneau de controle a ete ouvert.
) else (
  echo [BLOQUE] Voir %%LOCALAPPDATA%%\BazorAIROOM\oneshot_recovery.log
)
echo.
pause
exit /b %RC%
