# BAZOR TRI BUREAU + TELECHARGEMENTS — PREVISUALISATION puis CORBEILLE.
# Windows PowerShell 5.1, aucun module externe, aucune suppression definitive.
# NE TOUCHE PAS aux installations de %LOCALAPPDATA%, C:\AI, Ollama ou au depot GitHub.
param([switch]$PreviewOnly)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName Microsoft.VisualBasic
$Desktop = [Environment]::GetFolderPath('Desktop')
$Downloads = Join-Path $env:USERPROFILE 'Downloads'
$ReportDir = Join-Path $env:LOCALAPPDATA 'BAZOR\CleanupReports'
$RootRoom = Join-Path $env:LOCALAPPDATA 'BazorAIROOM'
$RootCore = Join-Path $env:LOCALAPPDATA 'BAZOR\Core'
$Repo = Join-Path $env:USERPROFILE 'bazor-mobile'
$NameUsefulFolder = 'BAZOR - RACCOURCIS VERIFIES'
$FinalFolder = Join-Path $Desktop $NameUsefulFolder
$script:Candidates = [System.Collections.ArrayList]::new()
$script:Protected = [System.Collections.ArrayList]::new()
$script:Seen = @{}
$script:CurrentCmdLines = @()
try {
    $script:CurrentCmdLines = @(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object { $_.CommandLine } | ForEach-Object { $_.CommandLine })
} catch { Write-Host '[INFO] Liste des commandes actives indisponible : prudence accrue.' }
$WS = New-Object -ComObject WScript.Shell
function Health([string]$URL) {
    try { return Invoke-RestMethod -Uri $URL -TimeoutSec 3 -ErrorAction Stop } catch { return $null }
}
function ResolveShortcut([string]$path) {
    try { return $WS.CreateShortcut($path) } catch { return $null }
}
function ReferencedByRunningProgram([string]$path) {
    # Empêche le recyclage d'un dossier qui héberge un programme encore en cours.
    foreach ($cmd in $script:CurrentCmdLines) {
        if ($cmd.IndexOf($path,[StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    }
    return $false
}
function HasProtectedContent([string]$dir) {
    # Modèles, données, vidéos, dépôts et secrets peuvent être uniques.
    try {
        if (Test-Path -LiteralPath (Join-Path $dir '.git')) { return $true }
        $files = @(Get-ChildItem -LiteralPath $dir -Recurse -File -Force -ErrorAction Stop |
            Where-Object { $_.Extension -match '^\.(mp4|mkv|mov|safetensors|gguf|ckpt|pt|pth|db|sqlite|sqlite3)$' -or $_.Name -match '^\.env($|\.)' } |
            Select-Object -First 1)
        return $files.Count -gt 0
    } catch { return $true }
}
function SizeOf([string]$path) {
    try {
        $x = Get-Item -LiteralPath $path -ErrorAction Stop
        if (-not $x.PSIsContainer) { return [long]$x.Length }
        # Taille de dossier informative; ne pas lire le contenu des fichiers.
        $sum = [long]0
        Get-ChildItem -LiteralPath $path -Recurse -File -ErrorAction Stop |
          ForEach-Object { $sum += [long]$_.Length }
        return $sum
    } catch { return [long]0 }
}
function AddProtected([string]$path,[string]$reason) {
    [void]$script:Protected.Add([pscustomobject]@{Path=$path;Raison=$reason})
}
function AddCandidate([string]$path,[string]$reason) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    if ($script:Seen.ContainsKey($path.ToLowerInvariant())) { return }
    $script:Seen[$path.ToLowerInvariant()] = $true
    $i = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    if (-not $i) { return }
    # Aucune jonction / aucun dossier lien symbolique traité.
    if ($i.PSIsContainer -and $i.LinkType -match '^(SymbolicLink|Junction|HardLink)$') {
       AddProtected $path 'Lien symbolique/jonction : cible non suivie'; return
    }
    if ($i.Attributes -band [IO.FileAttributes]::Offline) {
       AddProtected $path 'Element OneDrive indisponible localement'; return
    }
    if (ReferencedByRunningProgram $path) {
       AddProtected $path 'Référencé par un processus actif'; return
    }
    if ($i.PSIsContainer -and (HasProtectedContent $path)) {
       AddProtected $path 'Contient possiblement données, modèles, médias ou dépôt Git uniques'; return
    }
    [void]$script:Candidates.Add([pscustomobject]@{
      Path=$path; Nom=$i.Name; Raison=$reason;
      EstDossier=[bool]$i.PSIsContainer; Octets=(SizeOf $path)
    })
}

# S'assurer que le seul raccourci que nous classerons comme VERIFIE est réellement installé,
# lié à un lanceur protégé contre les doublons, et que Core et Room répondent maintenant.
$desktopRoom = Join-Path $Desktop 'BAZOR AI ROOM.lnk'
$roomLnk = if (Test-Path -LiteralPath $desktopRoom) { ResolveShortcut $desktopRoom } else { $null }
$coreHealth = Health 'http://127.0.0.1:8775/api/v1/health'
$roomHealth = Health 'http://127.0.0.1:8765/health'
$chatHealth = Health 'http://127.0.0.1:8765/api/chat/core'
$validRoom = $false
if ($roomLnk -and $coreHealth -and $roomHealth -and $chatHealth) {
    $target = [string]$roomLnk.TargetPath
    $args = [string]$roomLnk.Arguments
    $guard = Join-Path $env:LOCALAPPDATA 'BAZOR\Start\DEMARRER_BAZOR.ps1'
    if ((Test-Path -LiteralPath $target) -and
        ($target -match '(?i)powershell\.exe$') -and
        ($args.IndexOf($guard,[StringComparison]::OrdinalIgnoreCase) -ge 0) -and
        (Test-Path -LiteralPath $guard) -and
        ((Get-Content -LiteralPath $guard -Raw).Contains('BAZOR_DEMARRAGE_UNIQUE_20260926')) -and
        ($coreHealth.ok -eq $true) -and
        ($coreHealth.service -eq 'BAZOR API') -and
        ([string]$roomHealth.version -match '^3\.1\.') -and
        ($roomHealth.ok -eq $true) -and
        ($chatHealth.core -eq $true) -and
        ($chatHealth.ollama -eq $true)) { $validRoom=$true }
}
Write-Host ('[TEST] AI Room -> Core -> Ollama : ' + $(if($validRoom){'VERIFIE (sante HTTP + raccourci conforme)'}else{'NON VERIFIE - raccourci conserve a sa place'}))
Write-Host '[INFO] Ce test ne lance ni Studio ni les anciens Hub/Router.'

# Raccourcis Studio : ne garder qu'après une preuve de son endpoint et un fichier cible existant.
$studioLnkPath = Join-Path $Desktop 'AI Simple Studio 2.lnk'
$studioVerified = $false
if (Test-Path -LiteralPath $studioLnkPath) {
    $st = ResolveShortcut $studioLnkPath
    $studioHTTP = Health 'http://127.0.0.1:8191/'
    $comfyHTTP = Health 'http://127.0.0.1:8188/system_stats'
    if ($st -and (Test-Path -LiteralPath $st.TargetPath) -and $studioHTTP -and $comfyHTTP -and
        (Test-Path -LiteralPath 'C:\AI\SimpleStudioV2') -and
        (Test-Path -LiteralPath 'C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI')) {
        $studioVerified=$true
    }
}
Write-Host ('[TEST] Studio : ' + $(if($studioVerified){'ENDPOINTS 8191/8188 ET CIBLE PRESENTS'}else{'NON CERTIFIE : raccourci non detruit'}))

# Répertorier seulement les items à thème BAZOR du Bureau.
$desktopMask='(?i)^(BAZOR|INSTALLER.*BAZOR|PATCH_TOR_|REPARER_BAZOR_|TOR BAZOR)'
foreach ($x in @(Get-ChildItem -LiteralPath $Desktop -Force -ErrorAction SilentlyContinue)) {
    if ($x.FullName -eq $FinalFolder) { continue }
    if ($x.FullName -eq $desktopRoom) { continue }
    if ($x.FullName -eq $studioLnkPath) { continue }
    if ($x.Name -notmatch $desktopMask) { continue }
    if ($x.PSIsContainer -and $x.Name -match '(?i)BACKUP|SAUVEGARDE|TRANSFER') {
        AddProtected $x.FullName 'Sauvegarde potentiellement unique'; continue
    }
    if ($x.Name -match '(?i)MAMMOUTH_TRANSFER|BACKUP|SAUVEGARDE') {
        AddProtected $x.FullName 'Archive volumineuse de sauvegarde, non comparable à GitHub seul';continue
    }
    # L'ancien raccourci Hub n'est pas une preuve de version récente. On recycle
    # le lien, JAMAIS les fichiers du Hub/installations.
    AddCandidate $x.FullName 'Ancien item du Bureau BAZOR, applications installées conservées'
}
# Si Studio n'est pas opérationnel, son raccourci reste sur le Bureau pour ne pas
# donner un faux statut et éviter d'en priver Vincent avant un vrai test.
if (-not $studioVerified -and (Test-Path $studioLnkPath)) {
    AddProtected $studioLnkPath 'Studio non testé en fonctionnement; raccourci conservé hors dossier vérifié'
}
if (-not $validRoom -and (Test-Path $desktopRoom)) {
    AddProtected $desktopRoom 'Point d entrée BAZOR non confirmé; préservé sur le Bureau'
}

# Téléchargements : anciens packages installateurs, rapports, diagnostics, copies
# et dossiers décompressés BAZOR. Ne jamais effacer une installation connue du Hub.
$downloadsFiles='(?i)(BAZOR|PATCH_TOR|REPARER_BAZOR)'
$allowedExt=@('.zip','.cmd','.ps1','.txt','.log','.md','.png','.json')
foreach ($x in @(Get-ChildItem -LiteralPath $Downloads -File -Force -ErrorAction SilentlyContinue)) {
    if ($x.Name -notmatch $downloadsFiles -or $x.Extension.ToLowerInvariant() -notin $allowedExt) {continue}
    if ($x.Name -match '(?i)MAMMOUTH_TRANSFER|BACKUP|SAUVEGARDE|DONNEES|DATABASE') {
        AddProtected $x.FullName 'Archives ou données potentiellement uniques';continue
    }
    if ($x.Attributes -band [IO.FileAttributes]::Offline) {
        AddProtected $x.FullName 'Fichier cloud non disponible localement';continue
    }
    AddCandidate $x.FullName 'Ancien téléchargement BAZOR (rapport, kit, patch ou archive); installation séparée'
}
foreach ($x in @(Get-ChildItem -LiteralPath $Downloads -Directory -Force -ErrorAction SilentlyContinue)) {
    if ($x.Name -notmatch '(?i)^(BAZOR|INSTALLER.*BAZOR|PATCH_TOR|REPARER_BAZOR|QUARANTINE|QUARANTAINE)') {continue}
    if ($x.Name -match '(?i)BACKUP|SAUVEGARDE|TRANSFER') {
        AddProtected $x.FullName 'Sauvegarde potentiellement unique';continue
    }
    AddCandidate $x.FullName 'Ancien dossier BAZOR décompressé, rapport ou quarantaine dans Téléchargements'
}

# Autres anciennes quarantaines explicitement BAZOR à la racine du Bureau.
foreach ($x in @(Get-ChildItem -LiteralPath $Desktop -Directory -Force -ErrorAction SilentlyContinue)) {
    if ($x.Name -match '(?i)^(QUARANTINE|QUARANTAINE)([_ -].*)?$') {
        AddCandidate $x.FullName 'Ancienne quarantaine du Bureau'
    }
}

New-Item -Path $ReportDir -ItemType Directory -Force | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$report=Join-Path $ReportDir ("TRI_BAZOR_"+$stamp+".txt")
$before=[long]0
foreach($c in $Candidates){ $before += $c.Octets }
$ordered=@($Candidates | Sort-Object -Property Octets -Descending)
$summary=@(
  "TRI BAZOR $stamp",
  "Bureau: $Desktop",
  "Telechargements: $Downloads",
  "Dossier de raccourcis verifies: $FinalFolder",
  "AI Room validee : $validRoom",
  "Studio valide : $studioVerified",
  "Aucune application installee ni aucun autre dossier touche",
  "CANDIDATS A LA CORBEILLE : $($ordered.Count)",
  "TAILLE LOGIQUE : $([math]::Round($before/1GB,3)) Go",
  "",
  "CANDIDATS :"
)
$summary+=@($ordered | ForEach-Object { "$([math]::Round($_.Octets/1MB,1)) Mo | $($_.Path) | $($_.Raison)" })
# Contrôle rapide, sans extraction, de l'archive Mammouth du Bureau.
# Le dépôt GitHub a le code source, pas une preuve de redondance de cette sauvegarde locale.
$archiveCheck=@()
$transfer = @(Get-ChildItem -LiteralPath $Desktop -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '(?i)^BAZOR_MAMMOUTH_TRANSFER.*\.zip$' })
foreach ($zip in $transfer) {
    try {
        if ($zip.Attributes -band [IO.FileAttributes]::Offline) {
            $archiveCheck += "NON INSPECTE (OneDrive hors-ligne): $($zip.FullName)"
            continue
        }
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
        $z=[System.IO.Compression.ZipFile]::OpenRead($zip.FullName)
        try {
            $entries=@($z.Entries)
            $suspicious=@($entries | Where-Object { $_.FullName -match '(?i)(model|checkpoint|\.env|database|\.sqlite|\.db|\.gguf|\.safetensors|\.mp4)' })
            $archiveCheck += "$($zip.Name): $($entries.Count) entrees, $($suspicious.Count) noms de donnees/modeles/medias. A PRESERVER jusqu'a comparaison locale."
            $archiveCheck += @($entries | Select-Object -First 30 | ForEach-Object { "  " + $_.FullName })
        } finally { $z.Dispose() }
    } catch {
        $archiveCheck += "IMPOSSIBLE D INSPECTER: $($zip.Name) ($($_.Exception.Message)) : ARCHIVE PRESERVEE"
    }
}
$summary+=@("","INSPECTION ARCHIVE MAMMOUTH (sans suppression automatique):")
$summary+=@($archiveCheck)
$summary+=@("","PROTEGES / NON VERIFIES :")
$summary+=@($Protected | ForEach-Object { "$($_.Path) | $($_.Raison)" })
$summary | Set-Content -LiteralPath $report -Encoding UTF8
Write-Host ''
Write-Host '================= APERCU DU NETTOYAGE =================' -ForegroundColor Cyan
Write-Host ("A la Corbeille: {0} elements, taille logique {1} Go" -f $ordered.Count,[math]::Round($before/1GB,3))
Write-Host "Dossier de raccourcis verifies : $FinalFolder"
$ordered | Select-Object -First 35 @{N='Mo';E={[math]::Round($_.Octets/1MB,1)}},Nom,Raison | Format-Table -AutoSize
if ($ordered.Count -gt 35) { Write-Host "... +$($ordered.Count-35) autres elements (rapport complet)." }
Write-Host "Proteges/non verifies : $($Protected.Count)."
Write-Host "Rapport complet : $report"
Write-Host 'IMPORTANT: Le Bureau est synchronise a OneDrive; mettre un element a la Corbeille peut aussi le supprimer des autres appareils synchronises.' -ForegroundColor Yellow
Write-Host 'Le ZIP MAMMOUTH_TRANSFER, les installations et tout dossier contenant modèles/vidéos/DB sont protégés.'
if ($PreviewOnly) { Write-Host '[APERCU SEULEMENT] Aucun fichier deplace.';exit 0 }
Write-Host ''
$confirmation=Read-Host 'Pour envoyer CES candidats a la Corbeille et classer les raccourcis testes, tape CORBEILLE (sinon Entree)'
if ($confirmation -cne 'CORBEILLE') { Write-Host '[STOP] Aucun fichier envoye a la Corbeille.';exit 0 }

# Ne déplacer un raccourci que si l'état connu était vérifié pendant cet audit.
if ($validRoom -or $studioVerified) {
    New-Item -Path $FinalFolder -ItemType Directory -Force | Out-Null
}
if ($validRoom -and (Test-Path -LiteralPath $desktopRoom)) {
    Move-Item -LiteralPath $desktopRoom -Destination (Join-Path $FinalFolder 'BAZOR AI ROOM.lnk') -ErrorAction Stop
    Write-Host '[CONSERVE] Raccourci AI Room 3.1 teste, range dans le dossier verifie.' -ForegroundColor Green
}
if ($studioVerified -and (Test-Path -LiteralPath $studioLnkPath)) {
    Move-Item -LiteralPath $studioLnkPath -Destination (Join-Path $FinalFolder 'AI Simple Studio 2.lnk') -ErrorAction Stop
    Write-Host '[CONSERVE] Raccourci Studio, endpoints actifs, range.' -ForegroundColor Green
}
# Envoyer uniquement les objets prévisualisés ; conserver les échecs et les logs.
$sent=[long]0
$removed=0
foreach($c in $ordered) {
    if (-not (Test-Path -LiteralPath $c.Path)) {continue}
    if (ReferencedByRunningProgram $c.Path) { Write-Host "[SAUTE] Procesus en cours : $($c.Nom)";continue }
    try {
        if ($c.EstDossier) {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
                $c.Path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
            )
        } else {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                $c.Path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
            )
        }
        $removed++;$sent += [long]$c.Octets
        Write-Host ("[POUBELLE] " + $c.Nom) -ForegroundColor Green
    } catch {
        Write-Host ("[ECHEC, CONSERVE] " + $c.Nom + " : " + $_.Exception.Message) -ForegroundColor Yellow
    }
}
$result="RESULTAT: $removed elements envoyes a la Corbeille; $([math]::Round($sent/1GB,3)) Go logiques; espace recupere seulement apres vidage de la Corbeille."
Add-Content -LiteralPath $report -Value @("","$result") -Encoding UTF8
Write-Host $result -ForegroundColor Cyan
Write-Host "RAPPORT: $report"
