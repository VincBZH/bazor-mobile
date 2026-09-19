@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BAZOR STUDIO - WATCHER RECOVERY

set "ROOT=%USERPROFILE%\bazor-mobile"
set "WATCHER=%ROOT%\pc-relay\bazor_github_watcher.py"
set "SUPERVISOR=%ROOT%\pc-relay\bazor_watcher_supervisor.py"

if not exist "%ROOT%\.git" exit /b 2
cd /d "%ROOT%"

git fetch origin main >nul 2>&1
if errorlevel 1 exit /b 3
git pull --ff-only >nul 2>&1
if errorlevel 1 exit /b 4

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m py_compile "%WATCHER%" "%SUPERVISOR%" >nul 2>&1
  if errorlevel 1 exit /b 5
  set "PYEXE=py"
  set "PYARGS=-3"
) else (
  where python >nul 2>nul
  if errorlevel 1 exit /b 6
  python -m py_compile "%WATCHER%" "%SUPERVISOR%" >nul 2>&1
  if errorlevel 1 exit /b 7
  set "PYEXE=python"
  set "PYARGS="
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'bazor_github_watcher\.py|bazor_watcher_supervisor\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

%SystemRoot%\System32\timeout.exe /t 1 /nobreak >nul

if not exist "%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS" mkdir "%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$py=Get-Command pythonw.exe -ErrorAction SilentlyContinue; if($py){Start-Process -FilePath $py.Source -ArgumentList '\"%SUPERVISOR%\"' -WorkingDirectory '%ROOT%' -WindowStyle Hidden}else{Start-Process -FilePath 'python.exe' -ArgumentList '\"%SUPERVISOR%\"' -WorkingDirectory '%ROOT%' -WindowStyle Hidden}"

%SystemRoot%\System32\timeout.exe /t 4 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'bazor_watcher_supervisor\.py' }; $w=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'bazor_github_watcher\.py' }; if($s -and $w){exit 0}else{exit 1}"
if errorlevel 1 (
  echo [%DATE% %TIME%] WATCHER_START_FAILED>>"%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS\studio_watcher_boot.log"
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'bazor_watcher_supervisor\.py|bazor_github_watcher\.py' } | Select-Object ProcessId,CommandLine | Out-File -FilePath '%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS\studio_watcher_processes.txt' -Encoding utf8"
  exit /b 8
)

for /f %%H in ('git rev-parse HEAD 2^>nul') do set "HEADSHA=%%H"
echo [%DATE% %TIME%] WATCHER_START_OK head=%HEADSHA%>>"%ROOT%\pc-relay\BAZOR_DATA\HUB_LOGS\studio_watcher_boot.log"

exit /b 0
