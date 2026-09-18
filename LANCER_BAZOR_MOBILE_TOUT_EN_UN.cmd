@echo off
setlocal EnableExtensions
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
chcp 65001 >nul
title BAZOR - ONE CLICK
set "ROOT=%USERPROFILE%\bazor-mobile"
cd /d "%ROOT%"

where python >nul 2>nul || (echo [BLOQUE] Python introuvable.& pause& exit /b 1)
where git >nul 2>nul || (echo [BLOQUE] Git introuvable.& pause& exit /b 1)

git pull >nul 2>&1

if exist "%ROOT%\console-hub\bazor_mobile_network_repair.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\console-hub\bazor_mobile_network_repair.ps1" -Root "%ROOT%" >nul 2>&1
)

netsh advfirewall firewall delete rule name="BAZOR Mobile Core 8775" >nul 2>nul
netsh advfirewall firewall add rule name="BAZOR Mobile Core 8775" dir=in action=allow protocol=TCP localport=8775 profile=any remoteip=localsubnet >nul 2>nul
netsh advfirewall firewall delete rule name="BAZOR Mobile Web 8776" >nul 2>nul
netsh advfirewall firewall add rule name="BAZOR Mobile Web 8776" dir=in action=allow protocol=TCP localport=8776 profile=any remoteip=localsubnet >nul 2>nul

call "%ROOT%\LANCER_BAZOR_CONSOLE_HUB.cmd"
exit /b 0
