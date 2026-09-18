@echo off
setlocal
chcp 65001 >nul
set "ROOT=%USERPROFILE%\bazor-mobile"
if exist "%ROOT%\LANCER_BAZOR_CONSOLE_HUB.cmd" (
  start "" /b cmd /c ""%ROOT%\LANCER_BAZOR_CONSOLE_HUB.cmd""
  exit /b 0
)
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
  start "" /b python bazor_github_watcher.py
) else (
  start "" /b pythonw bazor_github_watcher.py
)
exit /b 0
