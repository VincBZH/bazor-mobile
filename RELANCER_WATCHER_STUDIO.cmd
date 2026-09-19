@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR STUDIO - WATCHER RECOVERY

set "ROOT=%USERPROFILE%\bazor-mobile"
set "WATCHER=%ROOT%\pc-relay\bazor_github_watcher.py"
set "LOG=%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS\watcher.log"

if not exist "%ROOT%\.git" exit /b 2
cd /d "%ROOT%"

git fetch origin main >nul 2>&1
if errorlevel 1 exit /b 3
git pull --ff-only >nul 2>&1
if errorlevel 1 exit /b 4

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m py_compile "%WATCHER%" >nul 2>&1
  if errorlevel 1 exit /b 5
  set "PYEXE=py"
  set "PYARGS=-3"
) else (
  where python >nul 2>nul
  if errorlevel 1 exit /b 6
  python -m py_compile "%WATCHER%" >nul 2>&1
  if errorlevel 1 exit /b 7
  set "PYEXE=python"
  set "PYARGS="
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'bazor_github_watcher\.py' }; if($p){exit 0}else{exit 1}"
if not errorlevel 1 exit /b 0

if not exist "%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS" mkdir "%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pw=Get-Command pythonw.exe -ErrorAction SilentlyContinue; if($pw){Start-Process -FilePath $pw.Source -ArgumentList '\"%WATCHER%\"' -WorkingDirectory '%ROOT%' -WindowStyle Hidden}else{Start-Process -FilePath 'python.exe' -ArgumentList '\"%WATCHER%\"' -WorkingDirectory '%ROOT%' -WindowStyle Hidden}"

%SystemRoot%\System32\timeout.exe /t 3 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'bazor_github_watcher\.py' }; if($p){exit 0}else{exit 1}"
if errorlevel 1 exit /b 8

exit /b 0
