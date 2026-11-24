@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title BAZOR - Hub central des outils
color 0B

set "ROOT=C:\BAZOR TOOL"
set "HUB=%ROOT%\Hub"
set "TOOLS=%HUB%\Outils"
set "LOG=%ROOT%\Logs\BAZOR_HUB_MENU.log"
if not exist "%ROOT%\Logs" md "%ROOT%\Logs" >nul 2>&1
call :log "OUVERTURE_MENU"

:MENU
cls
echo ============================================================
echo                 B A Z O R  -  H U B
echo ============================================================
echo   Outils locaux detectes et raccourcis centralises
echo   Une absence est affichee sans fermer le menu.
echo ------------------------------------------------------------

call :resolve_airoom
call :resolve_studio
call :resolve_comfy
call :resolve_autopilot
call :resolve_pc
call :resolve_panic
call :resolve_tor
call :resolve_wii
call :resolve_core
call :resolve_extractor
call :resolve_organizer

call :status "1  AI ROOM" AIROOM_TARGET
if exist "C:\AI\SimpleStudioV2" (echo [OK] 2  AI Simple Studio BAZOR) else (echo [--] 2  AI Simple Studio BAZOR)
call :status "3  ComfyUI GPU" COMFY_TARGET
call :status "4  BAZOR Autopilot V5" AUTOPILOT_TARGET
call :status "5  BAZOR PC Cleaner Ultimate" PC_TARGET
call :status "6  BAZOR PANIC (Cleaner)" PANIC_TARGET
call :status "7  TOR Model Scout / TOR" TOR_TARGET
call :status "8  Wii AI Relay" WII_TARGET
call :status "9  BAZOR Core" CORE_TARGET
call :status "10 ChatGPT Extractor" EXTRACTOR_TARGET
call :status "11 BAZOR Organizer" ORGANIZER_TARGET
echo.
echo [H] Ouvrir le dossier des raccourcis
echo [L] Ouvrir les logs et la quarantaine
echo [R] Reinstaller / actualiser le hub
echo [B] Ouvrir la racine C:\BAZOR TOOL
echo [0] Quitter
echo ------------------------------------------------------------
set "CHOIX="
set /p "CHOIX=Choix : "

if /i "!CHOIX!"=="0" exit /b 0
if /i "!CHOIX!"=="1" goto RUN_AIROOM
if /i "!CHOIX!"=="2" goto RUN_STUDIO
if /i "!CHOIX!"=="3" goto RUN_COMFY
if /i "!CHOIX!"=="4" goto RUN_AUTOPILOT
if /i "!CHOIX!"=="5" goto RUN_PC
if /i "!CHOIX!"=="6" goto RUN_PANIC_CONFIRMED
if /i "!CHOIX!"=="7" goto RUN_TOR
if /i "!CHOIX!"=="8" goto RUN_WII
if /i "!CHOIX!"=="9" goto RUN_CORE
if /i "!CHOIX!"=="10" goto RUN_EXTRACTOR
if /i "!CHOIX!"=="11" goto RUN_ORGANIZER
if /i "!CHOIX!"=="H" goto OPEN_TOOLS
if /i "!CHOIX!"=="L" goto OPEN_LOGS
if /i "!CHOIX!"=="R" goto REFRESH_HUB
if /i "!CHOIX!"=="B" goto OPEN_ROOT
goto MENU

:RUN_AIROOM
if defined AIROOM_TARGET (call :run_target "!AIROOM_TARGET!") else (call :missing "AI ROOM")
pause
goto MENU

:RUN_STUDIO
call :resolve_studio
if defined STUDIO_TARGET (
    call :run_target "!STUDIO_TARGET!"
) else if exist "C:\AI\SimpleStudioV2" (
    call :open_path "C:\AI\SimpleStudioV2"
) else (
    call :missing "AI Simple Studio BAZOR"
)
pause
goto MENU

:RUN_COMFY
call :open_comfy
pause
goto MENU

:RUN_AUTOPILOT
if defined AUTOPILOT_TARGET (call :run_target "!AUTOPILOT_TARGET!") else (call :missing "BAZOR Autopilot V5")
pause
goto MENU

:RUN_PC
if defined PC_TARGET (call :run_target "!PC_TARGET!") else (call :missing "BAZOR PC Cleaner Ultimate")
pause
goto MENU

:RUN_PANIC
if defined PANIC_TARGET (call :run_target "!PANIC_TARGET!") else (call :missing "BAZOR PANIC")
pause
goto MENU

:RUN_TOR
if defined TOR_TARGET (call :run_target "!TOR_TARGET!") else (call :missing "TOR Model Scout / TOR")
pause
goto MENU

:RUN_WII
if defined WII_TARGET (call :run_target "!WII_TARGET!") else (call :missing "Wii AI Relay")
pause
goto MENU

:RUN_CORE
if defined CORE_TARGET (call :run_target "!CORE_TARGET!") else (call :missing "BAZOR Core")
pause
goto MENU

:RUN_EXTRACTOR
if defined EXTRACTOR_TARGET (call :run_target "!EXTRACTOR_TARGET!") else (call :missing "ChatGPT Extractor")
pause
goto MENU

:RUN_ORGANIZER
if defined ORGANIZER_TARGET (call :run_target "!ORGANIZER_TARGET!") else (call :missing "BAZOR Organizer")
pause
goto MENU

:OPEN_TOOLS
call :open_path "%TOOLS%"
pause
goto MENU

:OPEN_LOGS
call :open_path "%ROOT%\Logs"
if exist "%LOCALAPPDATA%\BazorDiskCleaner\Quarantine\BAZOR" call :open_path "%LOCALAPPDATA%\BazorDiskCleaner\Quarantine\BAZOR"
pause
goto MENU

:REFRESH_HUB
if exist "%HUB%\INSTALLER_RACCOURCI_BAZOR.cmd" (
    start "" "%ComSpec%" /d /k call "%HUB%\INSTALLER_RACCOURCI_BAZOR.cmd"
    call :log "ACTUALISATION_HUB"
) else (
    echo Installateur central introuvable : %HUB%\INSTALLER_RACCOURCI_BAZOR.cmd
)
pause
goto MENU

:OPEN_ROOT
call :open_path "%ROOT%"
pause
goto MENU

:run_target
set "RUN_TARGET=%~1"
if not exist "!RUN_TARGET!" (
    call :missing "!RUN_TARGET!"
    exit /b 1
)
for %%E in ("!RUN_TARGET!") do set "RUN_EXT=%%~xE"
call :log "LANCEMENT=!RUN_TARGET!"
if /i "!RUN_EXT!"==".cmd" start "" "%ComSpec%" /d /k call "!RUN_TARGET!"
if /i "!RUN_EXT!"==".bat" start "" "%ComSpec%" /d /k call "!RUN_TARGET!"
if /i "!RUN_EXT!"==".ps1" start "" powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File "!RUN_TARGET!"
if /i "!RUN_EXT!"==".exe" start "" "!RUN_TARGET!"
if /i "!RUN_EXT!"==".lnk" start "" "!RUN_TARGET!"
exit /b 0

:open_comfy
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$c=New-Object Net.Sockets.TcpClient; try {$c.Connect('127.0.0.1',8188); Start-Process 'http://127.0.0.1:8188'; exit 0} catch {exit 1} finally {$c.Dispose()}" >nul 2>&1
if not errorlevel 1 (
    echo ComfyUI repond deja sur le port 8188 : ouverture dans le navigateur.
    call :log "COMFYUI_DEJA_ACTIF"
    exit /b 0
)
if defined COMFY_TARGET (
    call :run_target "!COMFY_TARGET!"
) else (
    call :missing "ComfyUI GPU"
)
exit /b 0

:open_path
set "OPEN_PATH=%~1"
if exist "!OPEN_PATH!" (
    start "" explorer.exe "!OPEN_PATH!"
    call :log "OUVERTURE_DOSSIER=!OPEN_PATH!"
) else (
    echo Dossier introuvable : !OPEN_PATH!
    call :log "DOSSIER_ABSENT=!OPEN_PATH!"
)
exit /b 0

:missing
echo [ABSENT] %~1 : aucun chemin local detecte.
call :log "OUTIL_ABSENT=%~1"
exit /b 0

:status
if defined %~2 (echo [OK] %~1) else (echo [--] %~1)
exit /b 0

:log
>>"%LOG%" echo [%date% %time%] %~1
exit /b 0

:resolve_airoom
set "TARGET="
for %%P in ("C:\Users\vgour\AppData\Local\BazorAIROOM\DEMARRER_BAZOR_AI_ROOM.cmd" "C:\BAZOR TOOL\AI ROOM\LANCER_BAZOR_AI_ROOM.cmd" "C:\BAZOR TOOL\AI_ROOM\LANCER_BAZOR_AI_ROOM.cmd" "C:\BAZOR TOOL\AI ROOM\START_BAZOR_AI_ROOM.cmd" "C:\BAZOR TOOL\AI ROOM\run.cmd" "C:\Users\vgour\AppData\Local\BazorAIROOM\run.cmd") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "AIROOM_TARGET=!TARGET!"
exit /b 0

:resolve_studio
set "TARGET="
for %%P in ("C:\Users\vgour\OneDrive\Desktop\AI Simple Studio BAZOR 2.2.lnk" "%USERPROFILE%\Desktop\AI Simple Studio BAZOR 2.2.lnk" "C:\AI\SimpleStudioV2\LANCER_BAZOR_STUDIO.cmd" "C:\AI\SimpleStudioV2\START_BAZOR_STUDIO.cmd" "C:\AI\SimpleStudioV2\LANCER_AI_SIMPLE_STUDIO.cmd" "C:\AI\SimpleStudioV2\start.cmd" "C:\AI\SimpleStudioV2\start.bat") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "STUDIO_TARGET=!TARGET!"
exit /b 0

:resolve_comfy
set "TARGET="
for %%P in ("C:\AI\ComfyUI\ComfyUI_windows_portable\run_nvidia_gpu.bat") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "COMFY_TARGET=!TARGET!"
exit /b 0

:resolve_autopilot
set "TARGET="
for %%P in ("C:\BAZOR TOOL\Autopilot\LANCER_AUTOPILOT_V5.cmd" "C:\BAZOR TOOL\Autopilot\START_AUTOPILOT_V5.cmd" "C:\BAZOR TOOL\Autopilot\AUTOPILOT_V5.cmd" "C:\BAZOR TOOL\Autopilot\AUTOPILOT.cmd" "C:\BAZOR TOOL\Autopilot\START_V5.cmd") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "AUTOPILOT_TARGET=!TARGET!"
exit /b 0

:resolve_pc
set "TARGET="
for %%P in ("%USERPROFILE%\OneDrive\Desktop\BAZOR_CLEANER.cmd" "%USERPROFILE%\Desktop\BAZOR_CLEANER.cmd") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "PC_TARGET=!TARGET!"
exit /b 0

:resolve_panic
set "TARGET="
for %%P in ("C:\BAZOR\PC_Cleaner\LANCER_PANIC.cmd") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "PANIC_TARGET=!TARGET!"
exit /b 0

:resolve_tor
set "TARGET="
for %%P in ("C:\BAZOR TOOL\TorModelScout\LANCER_BAZOR_TOR_MODEL_SCOUT.cmd" "C:\BAZOR TOOL\TOR\LANCER_TOR.cmd" "C:\BAZOR TOOL\TOR\LANCER_BAZOR_TOR_MODEL_SCOUT.cmd") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "TOR_TARGET=!TARGET!"
exit /b 0

:resolve_wii
set "TARGET="
for %%P in ("C:\projetWII\Wii_AI_Bridge\START_BRIDGE.cmd" "C:\projetWII\Wii_AI_Bridge\start_bridge.ps1") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "WII_TARGET=!TARGET!"
exit /b 0

:resolve_core
set "TARGET="
for %%P in ("C:\BAZOR TOOL\Core\DEMARRER_BAZOR_CORE.cmd" "C:\BAZOR TOOL\BAZOR CORE\DEMARRER_BAZOR_CORE.cmd" "C:\BAZOR TOOL\BAZOR_CORE\DEMARRER_BAZOR_CORE.cmd") do if not defined TARGET if exist "%%~P" set "TARGET=%%~P"
set "CORE_TARGET=!TARGET!"
exit /b 0

:resolve_extractor
set "TARGET="
for /f "delims=" %%P in ('dir /b /s "C:\BAZOR TOOL\*Extractor*.cmd" 2^>nul') do if not defined TARGET set "TARGET=%%P"
for /f "delims=" %%P in ('dir /b /s "C:\BAZOR TOOL\*Extractor*.exe" 2^>nul') do if not defined TARGET set "TARGET=%%P"
for /f "delims=" %%P in ('dir /b /s "C:\BAZOR\*Extractor*.cmd" 2^>nul') do if not defined TARGET set "TARGET=%%P"
for /f "delims=" %%P in ('dir /b /s "C:\BAZOR\*Extractor*.exe" 2^>nul') do if not defined TARGET set "TARGET=%%P"
set "EXTRACTOR_TARGET=!TARGET!"
exit /b 0

:resolve_organizer
set "TARGET="
for /f "delims=" %%P in ('dir /b /s "C:\BAZOR TOOL\BazorOrganizer.exe" 2^>nul') do if not defined TARGET set "TARGET=%%P"
set "ORGANIZER_TARGET=!TARGET!"
exit /b 0

