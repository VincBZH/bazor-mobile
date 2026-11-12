@echo off
if exist "%LOCALAPPDATA%\BAZOR\Veille\bazor_boot_watch.pyw" (
  pyw -3 "%LOCALAPPDATA%\BAZOR\Veille\bazor_boot_watch.pyw" --watch
) else (
  echo Installer d'abord BAZOR Veille.
  pause
)
