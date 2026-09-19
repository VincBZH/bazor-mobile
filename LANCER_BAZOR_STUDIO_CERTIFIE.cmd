@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR AI SIMPLE STUDIO CERTIFIE

set "ROOT=%USERPROFILE%\bazor-mobile"
set "SCRIPT=%ROOT%\console-hub\bazor_studio_certified_launcher.py"

echo ============================================================
echo   BAZOR AI SIMPLE STUDIO - LANCEMENT CERTIFIE
echo ============================================================
echo.

if not exist "%SCRIPT%" (
  echo [BLOQUE] Script absent:
  echo %SCRIPT%
  echo.
  pause
  exit /b 2
)

if exist "%ROOT%\RELANCER_WATCHER_STUDIO.cmd" (
  echo [STUDIO] Verification du watcher BAZOR...
  call "%ROOT%\RELANCER_WATCHER_STUDIO.cmd"
  if errorlevel 1 echo [INFO] Watcher non confirme, le lanceur Studio continue et gardera le diagnostic visible.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$script='%SCRIPT%';$py=$null;$launchArgs=@($script);" ^
  "$procs=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue;" ^
  "foreach($p in $procs){if(([string]$p.CommandLine) -match 'bazor_pc_relay_v3\.py' -and $p.ExecutablePath){$py=$p.ExecutablePath;break}};" ^
  "if(-not $py){$cmd=Get-Command py.exe -ErrorAction SilentlyContinue;if($cmd){$py=$cmd.Source;$launchArgs=@('-3',$script)}};" ^
  "if(-not $py){$cands=@($env:LOCALAPPDATA+'\Programs\Python\Python313\python.exe',$env:LOCALAPPDATA+'\Programs\Python\Python312\python.exe',$env:LOCALAPPDATA+'\Programs\Python\Python311\python.exe','C:\Python313\python.exe','C:\Python312\python.exe','C:\Python311\python.exe');foreach($cand in $cands){if(Test-Path $cand){$py=$cand;$launchArgs=@($script);break}}};" ^
  "if(-not $py){Write-Host '[BLOQUE] Python BAZOR introuvable.' -ForegroundColor Red;exit 11};" ^
  "Write-Host ('Python: '+$py);" ^
  "& $py @launchArgs;exit $LASTEXITCODE"

set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [OK] STUDIO CERTIFIE ET OUVERT.
) else (
  echo [BLOQUE] Le Studio n'a pas passe la certification. Code %RC%.
)
echo.
if "%BAZOR_STUDIO_NO_PAUSE%"=="1" goto :END
echo Cette fenetre reste ouverte pour le diagnostic.
pause
:END
exit /b %RC%
