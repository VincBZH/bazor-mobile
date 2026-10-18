# BAZOR - installation d'un lanceur unique sans redemarrages en double.
# Ne modifie aucun service Windows, demarrage automatique ou fichier de donnees.
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA 'BAZOR\Start'
$core = Join-Path $env:LOCALAPPDATA 'BAZOR\Core\bazor_pc_relay_v3.py'
$room = Join-Path $env:LOCALAPPDATA 'BazorAIROOM\app.py'
$desktop = [Environment]::GetFolderPath('Desktop')
$link = Join-Path $desktop 'BAZOR AI ROOM.lnk'
$backup = Join-Path $env:LOCALAPPDATA 'BazorAIROOM\Backups'
try {
    if (-not (Test-Path -LiteralPath $core -PathType Leaf)) { throw "Core introuvable : $core" }
    if (-not (Test-Path -LiteralPath $room -PathType Leaf)) { throw "Room introuvable : $room" }
    if (-not (Test-Path -LiteralPath $link -PathType Leaf)) { throw "Raccourci AI Room introuvable : $link" }
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python introuvable' }
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    $launcher = Join-Path $root 'DEMARRER_BAZOR.ps1'
    $source = @'
$ErrorActionPreference = "Stop"
$root = Join-Path $env:LOCALAPPDATA "BAZOR\Start"
$core = Join-Path $env:LOCALAPPDATA "BAZOR\Core\bazor_pc_relay_v3.py"
$room = Join-Path $env:LOCALAPPDATA "BazorAIROOM\app.py"
$state = Join-Path $root "DERNIER_DEMARRAGE.txt"
$mutex = New-Object System.Threading.Mutex($false, "Local\BAZOR_DEMARRAGE_UNIQUE_20260926")
if (-not $mutex.WaitOne(0)) { exit 0 }
function Log([string]$v) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),$v) | Add-Content -LiteralPath $state -Encoding UTF8 }
function Fail([string]$v) {
    Log ("BLOQUE: " + $v)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(($v + [Environment]::NewLine + "Consulte : " + $state),"BAZOR - demarrage bloque") | Out-Null
    } catch { Write-Host $v }
    exit 1
}
function CoreOK {
    try {
        $r=Invoke-RestMethod -Uri "http://127.0.0.1:8775/api/v1/health" -TimeoutSec 2
        return ($r.ok -eq $true -and $r.service -eq "BAZOR API")
    } catch { return $false }
}
function RoomOK {
    try {
        $r=Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 2
        return ($r.ok -eq $true -and [string]$r.version -match "^3\.1\.")
    } catch { return $false }
}
function Busy([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}
function StartLocal([string]$name,[string]$py,[string]$script) {
    $cmd = '$host.UI.RawUI.WindowTitle="BAZOR ' + $name + '"; & "' + $py + '" -u "' + $script + '"'
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))
    Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList @("-NoProfile","-NoExit","-EncodedCommand",$enc) -WindowStyle Minimized | Out-Null
    Log ("Lancement unique de " + $name)
}
function WaitOK([scriptblock]$check) {
    for ($i=0;$i -lt 40;$i++) {
        if (& $check) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}
try {
    Set-Content -LiteralPath $state -Value ("BAZOR " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Encoding UTF8
    if (-not (Test-Path -LiteralPath $core)) { Fail "Core introuvable" }
    if (-not (Test-Path -LiteralPath $room)) { Fail "AI Room introuvable" }
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) { Fail "Python introuvable" }
    if (-not (CoreOK)) {
        if (Busy 8775) { Fail "Port 8775 utilise par un service non valide. Rien relance." }
        StartLocal "CORE" $py $core
        if (-not (WaitOK { CoreOK })) { Fail "Core ne repond pas. Ouvre la fenetre BAZOR CORE." }
    } else { Log "Core deja actif, aucun doublon" }
    if (-not (RoomOK)) {
        if (Busy 8765) { Fail "Port 8765 utilise par une autre version Room. Rien relance." }
        StartLocal "AI ROOM" $py $room
        if (-not (WaitOK { RoomOK })) { Fail "Room ne repond pas. Ouvre la fenetre BAZOR AI ROOM." }
    } else { Log "Room deja active, aucun doublon" }
    $opera = Join-Path $env:LOCALAPPDATA "Programs\Opera\opera.exe"
    if (-not (Test-Path -LiteralPath $opera)) {
        $opera = "C:\Program Files\Opera\launcher.exe"
    }
    if (-not (Test-Path -LiteralPath $opera)) { Fail "Opera introuvable, mais Core et Room fonctionnent" }
    Start-Process -FilePath $opera -ArgumentList "http://127.0.0.1:8765/" | Out-Null
    Log "OK: Core + AI Room verifies; ouverture dans Opera"
} catch {
    Fail $_.Exception.Message
} finally {
    if ($mutex) { try { $mutex.ReleaseMutex() } catch {}; $mutex.Dispose() }
}
'@
    [System.IO.File]::WriteAllText($launcher, $source, (New-Object System.Text.UTF8Encoding($false)))
    $snapshot = Join-Path $backup ("RACCOURCI_OPERA_AVANT_1_CLIC_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + ".lnk")
    Copy-Item -LiteralPath $link -Destination $snapshot
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($link)
    $s.TargetPath = "$PSHOME\powershell.exe"
    $s.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $launcher + '"'
    $s.WorkingDirectory = $root
    $s.WindowStyle = 7
    $operaIcon = Join-Path $env:LOCALAPPDATA 'Programs\Opera\opera.exe'
    if (Test-Path -LiteralPath $operaIcon) { $s.IconLocation = "$operaIcon,0" }
    $s.Description = 'BAZOR 1 clic : Core + Room (anti-doublon) + Opera'
    $s.Save()
    Write-Host '[OK] Le raccourci BAZOR AI ROOM ouvre Core + Room si absents, puis Opera.'
    Write-Host '[OK] Aucun service Windows ni demarrage automatique modifie.'
    Write-Host "[SAUVEGARDE] $snapshot"
    Write-Host '[TEST] Double-clique sur BAZOR AI ROOM une fois. Les services deja actifs ne seront pas relances.'
} catch {
    Write-Host ('[BLOQUE] ' + $_.Exception.Message)
    Write-Host 'Aucun ancien processus arrete. Ne relance pas un autre installateur.'
    exit 1
}
