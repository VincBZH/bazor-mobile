# BAZOR - Tri cible sur inventaire du 26/09/2026. CORBEILLE, aucune quarantaine.
# A lancer dans Windows PowerShell 5.1. PREVIEW puis confirmation explicite.
# Ne jamais toucher a C:\AI, %LOCALAPPDATA%\BAZOR\Core, Room, Ollama, ni aux depots.
param([switch]$ApercuSeul)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName Microsoft.VisualBasic
$desktop = [Environment]::GetFolderPath('Desktop')
$downloads = Join-Path $env:USERPROFILE 'Downloads'
$reportDir = Join-Path $env:LOCALAPPDATA 'BAZOR\CleanupReports'
$source = Join-Path $reportDir 'TRI_BAZOR_20260926_191026.txt'
$docRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'BAZOR'
$keepDir = Join-Path $docRoot 'Rapports_Studio_20260925'
$backupDir = Join-Path $docRoot 'Sauvegardes'
$shortcutDir = Join-Path $desktop 'BAZOR - RACCOURCIS VERIFIES'
$roomShortcut = Join-Path $desktop 'BAZOR AI ROOM.lnk'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
  throw "Inventaire original absent : $source. Aucun fichier touche."
}
$lines = @(Get-Content -LiteralPath $source -Encoding UTF8)
$entries = New-Object 'System.Collections.Generic.List[object]'
$reading = $false
foreach($line in $lines) {
  if ($line -eq 'CANDIDATS :') {$reading=$true;continue}
  if ($line -like 'INSPECTION ARCHIVE MAMMOUTH*') {break}
  if (-not $reading) {continue}
  if ($line -match '^[\d.,]+\s+Mo\s+\|\s+(C:\\[^|]+)\s+\|') {
    $p=$Matches[1].Trim()
    if ($p.StartsWith($desktop+'\',[StringComparison]::OrdinalIgnoreCase) -or
        $p.StartsWith($downloads+'\',[StringComparison]::OrdinalIgnoreCase)) {
      $entries.Add($p)
    }
  }
}
if ($entries.Count -ne 389) {
  throw "Inventaire incomplet ($($entries.Count)/389). Aucun nettoyage."
}
$w=New-Object -ComObject WScript.Shell
$coreOK=$false;$roomOK=$false
try {
  $c=Invoke-RestMethod 'http://127.0.0.1:8775/api/v1/health' -TimeoutSec 3 -ErrorAction Stop
  $r=Invoke-RestMethod 'http://127.0.0.1:8765/health' -TimeoutSec 3 -ErrorAction Stop
  $cr=Invoke-RestMethod 'http://127.0.0.1:8765/api/chat/core' -TimeoutSec 3 -ErrorAction Stop
  $coreOK=($c.ok -eq $true -and $c.service -eq 'BAZOR API')
  $roomOK=($r.ok -eq $true -and [string]$r.version -match '^3\.1\.' -and
           $cr.core -eq $true -and $cr.ollama -eq $true)
} catch {}
$guard = Join-Path $env:LOCALAPPDATA 'BAZOR\Start\DEMARRER_BAZOR.ps1'
$roomLinkOK=$false
if ($coreOK -and $roomOK -and (Test-Path -LiteralPath $guard) -and
    (Test-Path -LiteralPath $roomShortcut)) {
  try {
    $lnk=$w.CreateShortcut($roomShortcut)
    $roomLinkOK=([string]$lnk.TargetPath -match '(?i)powershell\.exe$' -and
      [string]$lnk.Arguments -like ('*'+$guard+'*') -and
      (Get-Content -LiteralPath $guard -Raw).Contains('BAZOR_DEMARRAGE_UNIQUE_20260926'))
  } catch {}
}
if (-not $roomLinkOK) {throw 'AI Room/Core/port 8765 ou raccourci non verifies : tri bloque, aucun fichier touche.'}
Write-Host '[OK] Raccourci + Core 8775 + AI Room 3.1 8765 + Ollama verifies.' -ForegroundColor Green
$proc = @()
try {$proc = @(Get-CimInstance Win32_Process -ErrorAction Stop |
  Where-Object CommandLine | ForEach-Object {$_.CommandLine})} catch {}
$taskRefs=@()
try {
  $taskRefs=@(Get-ScheduledTask -ErrorAction Stop | ForEach-Object {
    $_.Actions | ForEach-Object { [string]$_.Execute + ' ' + [string]$_.Arguments }
  })
} catch {Write-Host '[NOTE] Taches programmees non consultables : seuls les chemins manifestement anciens seront proposes.'}
$refText = @($proc+$taskRefs)
function IsReferenced([string]$path) {
  foreach ($str in $refText) {
    if ($str -and $str.IndexOf($path,[StringComparison]::OrdinalIgnoreCase) -ge 0) {return $true}
  }
  return $false
}
function UnsafeFolder([string]$path) {
  try {
    $i=Get-Item -LiteralPath $path -ErrorAction Stop
    if ($i.Attributes -band [IO.FileAttributes]::ReparsePoint) {return $true}
    if (Test-Path -LiteralPath (Join-Path $path '.git')) {return $true}
    $v=Get-ChildItem -LiteralPath $path -File -Force -Recurse -ErrorAction Stop |
       Where-Object {$_.Extension -match '^\.(mp4|mkv|mov|mp3|safetensors|gguf|ckpt|pt|pth|db|sqlite|sqlite3)$' -or
                     $_.Name -match '^(?i)\.env($|\.)'} | Select-Object -First 1
    return [bool]$v
  } catch {return $true}
}
function Category([string]$path) {
  $name = Split-Path -Path $path -Leaf
  $isDesk = $path.StartsWith($desktop+'\',[StringComparison]::OrdinalIgnoreCase)
  # Actifs, correctifs tres recents, codes non reproduits sur GitHub : ne pas supposer obsolete.
  if ($name -match '(?i)^(BAZOR_PAPA_OURS_PC_|BAZOR_ROUTER_V13(?:\b|[ ._(])|BAZOR_M3C|BAZOR_M3B|BAZOR_M3_A_ME|BAZOR_M3_VS|BAZOR_M3_PONY|BAZOR_MAMMOUTH_BRIDGE_V2|BAZOR_WII_BRIDGE_SAFE_V3|BAZOR_MONTRE_1\.2\.0|BAZOR_TOR_SECURITY_V8_2_1|BAZOR_NOTRACK_AUTO|BAZOR_MAMMOUTH_GO)') {
    if ($isDesk) {return 'ARCHIVE_STUDIO'}
    return 'GARDER'
  }
  if ($isDesk) {
    if ($name -match '(?i)^BAZOR_PREUVES_COMFYUI|^BAZOR_M3_REPORTS') {return 'ARCHIVE_STUDIO'}
    # Tous les vieux raccourcis ont une sauvegarde via Corbeille ; les binaires installes ne bougent pas.
    if ($name -match '(?i)\.lnk$') {return 'CORBEILLE'}
    if ($name -match '(?i)^BAZOR_AUDIT_TELECHARGEMENTS|^BAZOR_M[012](_|$)|^BAZOR_AI_FIX_|^INSTALLER_.*BAZOR|^BAZOR_TABLEAU_WEB_|^BAZOR_DISQUE_|^BAZOR_TRI_') {return 'CORBEILLE'}
    return 'GARDER'
  }
  # Les documents techniques de reference peuvent etre uniques. Ne pas effacer sans empreinte comparee.
  if ($name -match '(?i)\.(md|json|png|txt)$' -and $name -notmatch '(?i)^(BAZOR_.*(AUDIT|DIAGNOSTIC|_LOG|DISQUE_COMPLET|TRI_DOWNLOADS|BOOT_DIAG).*)') {return 'GARDER'}
  # Dernier lanceur Studio du depot peut rester utile tant que Studio n'a pas passe son test.
  if ($name -match '(?i)^LANCER_BAZOR_STUDIO_CERTIFIE\.cmd$') {return 'GARDER'}
  return 'CORBEILLE'
}
$toBin=New-Object 'System.Collections.Generic.List[object]'
$toArchive=New-Object 'System.Collections.Generic.List[object]'
$protected=New-Object 'System.Collections.Generic.List[string]'
$items = @($entries | Select-Object -Unique)
foreach($path in $items) {
  if (-not (Test-Path -LiteralPath $path)) {continue}
  $i=Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
  if (-not $i) {continue}
  if ($i.Attributes -band [IO.FileAttributes]::Offline) {
    $protected.Add("ONEDRIVE HORS LIGNE : "+$path);continue
  }
  if (IsReferenced $path) {
    $protected.Add("PROGRAMME OU TACHE UTILISE CE CHEMIN : "+$path);continue
  }
  $category=Category $path
  if ($category -eq 'GARDER') {
    $protected.Add("PROJET OU DOCUMENT A CONSERVER : "+$path);continue
  }
  if ($i.PSIsContainer -and (UnsafeFolder $path)) {
    $protected.Add("DOSSIER CONTIENT DONNEES/MEDIAS/MODELES OU LIEN : "+$path);continue
  }
  $obj=[pscustomobject]@{Path=$path;Nom=$i.Name;IsDir=[bool]$i.PSIsContainer;Bytes=[long]0}
  if (-not $i.PSIsContainer) {$obj.Bytes=[long]$i.Length}
  else {try{$v=[long]0;Get-ChildItem -LiteralPath $path -Recurse -File -ErrorAction Stop |
     ForEach-Object {$v += [long]$_.Length};$obj.Bytes=$v}catch{}}
  if ($category -eq 'ARCHIVE_STUDIO') {$toArchive.Add($obj)}
  else {$toBin.Add($obj)}
}
# Deux dossiers récents que l'audit initial a exclus car ils contiennent des medias :
# on les déplace dans Documents mais on ne les supprime JAMAIS.
foreach ($n in @('BAZOR_M3B_REPORTS','BAZOR_M3_REPORTS')) {
  $p = Join-Path $desktop $n
  if (Test-Path -LiteralPath $p -PathType Container) {
    $i = Get-Item -LiteralPath $p -Force
    if (($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        ($i.Attributes -band [IO.FileAttributes]::Offline) -or (IsReferenced $p)) {
      $protected.Add("DOSSIER STUDIO PROTEGE NON DEPLACE : "+$p)
    } else {
      $obj=[pscustomobject]@{Path=$p;Nom=$i.Name;IsDir=$true;Bytes=[long]0}
      $toArchive.Add($obj)
    }
  }
}
# Lien Studio non certifie : seulement le lien va a la corbeille, jamais Studio installe.
$studioLink=Join-Path $desktop 'AI Simple Studio 2.lnk'
if (Test-Path -LiteralPath $studioLink) {
  $i=Get-Item -LiteralPath $studioLink
  $toBin.Add([pscustomobject]@{Path=$studioLink;Nom=$i.Name;IsDir=$false;Bytes=[long]$i.Length})
}
# L'archive Mammouth contient 16568 entrees, dont des modeles/medias et sous-archives :
# non prouvee redondante avec GitHub, on la range dans les Sauvegardes des Documents.
$mammouth=Join-Path $desktop 'BAZOR_MAMMOUTH_TRANSFER_20260916.zip'
$moveMammouth=$false
if (Test-Path -LiteralPath $mammouth -PathType Leaf) {
  $mi=Get-Item -LiteralPath $mammouth
  if (-not ($mi.Attributes -band [IO.FileAttributes]::Offline) -and -not (IsReferenced $mammouth)) {
    $moveMammouth=$true
  } else {$protected.Add("MAMMOUTH ZIP RESTE SUR BUREAU (hors ligne/ouvert) : "+$mammouth)}
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$destReport=Join-Path $reportDir ("TRI_PHASE2_"+$stamp+".txt")
$binBytes=[long]0;foreach($x in $toBin){$binBytes += $x.Bytes}
$log=@(
 "TRI BAZOR PHASE2 "+$stamp,
 "INVENTAIRE SOURCE "+$source,
 "AI ROOM + CORE + OLLAMA + RACCOURCI : VERIFIES",
 "CORBEILLE : "+$toBin.Count+" objets; "+[math]::Round($binBytes/1MB,1)+" Mo",
 "ARCHIVE STUDIO : "+$toArchive.Count+" objets",
 "DEPLACEMENT ZIP MAMMOUTH : "+$moveMammouth,
 "GARDES : "+$protected.Count,
 "",
 "CORBEILLE :"
)
$log+=@($toBin | ForEach-Object {$_.Path})
$log+=@("","ARCHIVE STUDIO :")
$log+=@($toArchive | ForEach-Object {$_.Path})
$log+=@("","GARDES ET RAISONS :")
$log+=@($protected)
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$log | Set-Content -LiteralPath $destReport -Encoding UTF8
Write-Host ''
Write-Host "====== TRI BAZOR CIBLE (PREVISUALISATION) ======" -ForegroundColor Cyan
Write-Host ("CORBEILLE : {0} objets, {1} Mo" -f $toBin.Count,[math]::Round($binBytes/1MB,1))
Write-Host ("DOCUMENTS\BAZOR\Rapports_Studio : {0} dossiers/fichiers conserves" -f $toArchive.Count)
Write-Host ("MAMMOUTH TRANSFER : {0}" -f $(if($moveMammouth){'DEPLACE DANS DOCUMENTS\BAZOR\SAUVEGARDES, NON SUPPRIME'}else{'CONSERVE SUR BUREAU'}))
Write-Host ("AUTRES PROTEGES : {0}" -f $protected.Count)
Write-Host '[TEST] Ancien raccourci Studio : non certifie, seul son lien est propose a la Corbeille.'
Write-Host '[TEST] Ancien raccourci Hub : non certifie, seul son lien est propose a la Corbeille.'
Write-Host 'RAPPORT DETAILLE : ' $destReport
Write-Host 'Attention : les suppressions du Bureau OneDrive seront repercutees par la synchronisation.' -ForegroundColor Yellow
if ($ApercuSeul) {Write-Host '[APERÇU] Rien n a bouge.';exit 0}
$confirmation=Read-Host 'Pour confirmer UNIQUEMENT cette selection, ecris CORBEILLE'
if ($confirmation -cne 'CORBEILLE') {Write-Host '[STOP] Aucun element deplace ou supprime.';exit 0}
function SafeMove([string]$from,[string]$destination) {
  if (-not (Test-Path -LiteralPath $from)) {return}
  if (IsReferenced $from) {Write-Host ('[SAUTE, EN UTILISATION] '+$from);return}
  New-Item -ItemType Directory -Path $destination -Force | Out-Null
  $name=Split-Path -Path $from -Leaf
  $dest=Join-Path $destination $name
  if (Test-Path -LiteralPath $dest) {
    Write-Host ('[SAUTE, FICHIER EXISTANT] '+$dest) -ForegroundColor Yellow;return
  }
  try {
    Move-Item -LiteralPath $from -Destination $dest -ErrorAction Stop
    Write-Host ('[CONSERVE DANS DOCUMENTS] '+$name) -ForegroundColor Green
  } catch {Write-Host ('[ECHEC CONSERVE] '+$from+' '+$_.Exception.Message) -ForegroundColor Yellow}
}
# Dossier de raccourcis : le test dynamique ci-dessus a reussi; ne pas recreer les vieux raccourcis.
if (Test-Path -LiteralPath $roomShortcut) {
  New-Item -ItemType Directory -Path $shortcutDir -Force | Out-Null
  $dest=Join-Path $shortcutDir 'BAZOR AI ROOM.lnk'
  if (-not (Test-Path -LiteralPath $dest)) {
     Move-Item -LiteralPath $roomShortcut -Destination $dest -ErrorAction Stop
     Write-Host '[OK] AI ROOM RANGEE : RACCOURCI VERIFIE.' -ForegroundColor Green
  } else {Write-Host '[ATTENTION] Raccourci deja present dans le dossier verifie; original conserve.'}
}
foreach($x in $toArchive){SafeMove $x.Path $keepDir}
if ($moveMammouth) {
  # Ne pas copier 4,85 Go vers un autre disque sans consentement.
  if ([IO.Path]::GetPathRoot($mammouth) -eq [IO.Path]::GetPathRoot($backupDir)) {
    SafeMove $mammouth $backupDir
  } else {Write-Host '[SAUTE] Le ZIP Mammouth serait copie sur un autre disque; conserve.'}
}
$done=0;[long]$bytes=0
foreach($x in $toBin){
  if (-not (Test-Path -LiteralPath $x.Path)) {continue}
  if (IsReferenced $x.Path){Write-Host '[SAUTE ACTIF] ' $x.Nom;continue}
  try {
    if($x.IsDir){
      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
        $x.Path,
        [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
        [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
      )
    } else {
      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
        $x.Path,
        [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
        [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
      )
    }
    $done++;$bytes += [long]$x.Bytes
    Write-Host '[CORBEILLE] ' $x.Nom
  } catch {Write-Host ('[ECHEC, NON SUPPRIME] '+$x.Path+' '+$_.Exception.Message) -ForegroundColor Yellow}
}
$last=("TERMINE: "+$done+" objets a la Corbeille; "+[math]::Round($bytes/1MB,1)+" Mo (liberes apres vidage).")
Write-Host $last -ForegroundColor Green
Add-Content -LiteralPath $destReport -Value @("",$last) -Encoding UTF8
Write-Host "RAPPORT : $destReport"
