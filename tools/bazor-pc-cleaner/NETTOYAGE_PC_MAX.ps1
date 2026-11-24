# BAZOR PC Cleaner Ultimate compatibility launcher.
# Historical NETTOYAGE_PC_MAX implementation is archived as .source.txt and is not executable.
$ErrorActionPreference = 'Stop'
$Cleaner = 'C:\BAZOR\PC_Cleaner\BAZOR_PC_CLEANER.py'
if (-not (Test-Path -LiteralPath $Cleaner)) { throw "Cleaner source not found: $Cleaner" }
$Python = Get-Command pythonw -ErrorAction SilentlyContinue
if ($Python) { Start-Process -FilePath $Python.Source -ArgumentList @($Cleaner); exit 0 }
$Pyw = Get-Command pyw -ErrorAction SilentlyContinue
if ($Pyw) { Start-Process -FilePath $Pyw.Source -ArgumentList @('-3', $Cleaner); exit 0 }
throw 'Pythonw/pyw not found; nothing was cleaned.'
