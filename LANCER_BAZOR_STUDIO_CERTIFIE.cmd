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

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$script='%SCRIPT%';" ^
  "$py=$null;" ^
  "$p=Get-CimInstance Win32_Process ^| Where-Object { ([string]$_.CommandLine) -match 'bazor_pc_relay_v3\.py' -and $_.ExecutablePath } ^| Select-Object -First 1;" ^
  "if($p){$py=$p.ExecutablePath};" ^
  "if(-not $py){$cmd=Get-Command py.exe -ErrorAction SilentlyContinue;if($cmd){$py=$cmd.Source;$args=@('-3',$script)}else{$args=@($script)}}else{$args=@($script)};" ^
  "if(-not $py){$cands=@($env:LOCALAPPDATA+'\Programs\Python\Python313\python.exe',$env:LOCALAPPDATA+'\Programs\Python\Python312\python.exe',$env:LOCALAPPDATA+'\Programs\Python\Python311\python.exe','C:\Python313\python.exe','C:\Python312\python.exe','C:\Python311\python.exe');$py=$cands ^| Where-Object { Test-Path $_ } ^| Select-Object -First 1;$args=@($script)};" ^
  "if(-not $py){Write-Host '[BLOQUE] Python BAZOR introuvable.' -ForegroundColor Red;exit 11};" ^
  "Write-Host ('Python: '+$py);" ^
  "& $py @args;exit $LASTEXITCODE"

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
