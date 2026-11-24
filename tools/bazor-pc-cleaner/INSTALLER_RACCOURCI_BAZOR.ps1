#requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Root = 'C:\BAZOR TOOL'
$Hub = Join-Path $Root 'Hub'
$Tools = Join-Path $Hub 'Outils'
$LogDir = Join-Path $Root 'Logs'
$Quarantine = Join-Path $env:LOCALAPPDATA 'BazorDiskCleaner\Quarantine\BAZOR\HUB'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunQuarantine = Join-Path $Quarantine $Stamp
$LogFile = Join-Path $LogDir 'BAZOR_HUB_INSTALL.log'
$SystemeAccent = 'Syst' + [char]0x00e8 + 'me'

function Write-BazorLog {
    param(
        [Parameter(Mandatory = $true)][string]$What,
        [Parameter(Mandatory = $true)][string]$Why,
        [string]$By = 'BAZOR'
    )

    $line = '[{0}] | QUOI={1} | POURQUOI={2} | PAR={3}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $What, $Why, $By
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Get-FirstExisting {
    param([string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (Test-Path -LiteralPath $candidate) {
            return (Get-Item -LiteralPath $candidate).FullName
        }
    }
    return $null
}

function Get-ExtractorCandidate {
    $bases = @($Root, 'C:\BAZOR')
    foreach ($base in $bases) {
        if (-not (Test-Path -LiteralPath $base)) { continue }
        $found = Get-ChildItem -LiteralPath $base -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -match 'Extractor' -and
                $_.Extension -in @('.cmd', '.bat', '.exe', '.ps1') -and
                $_.FullName -notmatch '\\(Quarantine|Archives)(\\|$)'
            } |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

function Get-DesktopPath {
    $desktop = [Environment]::GetFolderPath('Desktop')
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        $desktop = Join-Path $env:USERPROFILE 'Desktop'
    }
    return $desktop
}

function Backup-Existing {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return }
    $destination = Join-Path $RunQuarantine ([IO.Path]::GetFileName($Path))
    New-Item -ItemType Directory -Path $RunQuarantine -Force | Out-Null
    Copy-Item -LiteralPath $Path -Destination $destination -Force
    Write-BazorLog -What "ARCHIVE=$Path -> $destination" -Why 'Conserver la version precedente avant mise a jour' -By 'BAZOR_INSTALLER'
}

function Install-ManagedFile {
    param([Parameter(Mandatory = $true)][string]$Name)

    $source = Join-Path $PSScriptRoot $Name
    $destination = Join-Path $Hub $Name
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Fichier requis introuvable : $source"
    }

    $sameFile = $false
    try {
        $sameFile = ([IO.Path]::GetFullPath($source) -ieq [IO.Path]::GetFullPath($destination))
    } catch {
        $sameFile = $false
    }

    if ($sameFile) {
        Write-BazorLog -What "CONSERVE=$destination" -Why 'Le lanceur est deja dans son emplacement central' -By 'BAZOR_INSTALLER'
        return
    }

    Backup-Existing -Path $destination
    Copy-Item -LiteralPath $source -Destination $destination -Force
    Write-BazorLog -What "INSTALL=$destination" -Why 'Installer le hub central BAZOR et son menu' -By 'BAZOR_INSTALLER'
}

function New-BazorLink {
    param(
        [Parameter(Mandatory = $true)][string]$Destination,
        [AllowEmptyString()][string]$Target,
        [Parameter(Mandatory = $true)][string]$Description
    )

    if ([string]::IsNullOrWhiteSpace($Target) -or -not (Test-Path -LiteralPath $Target)) {
        Write-BazorLog -What "ABSENT=$Description" -Why "Aucun lanceur local detecte pour $Description" -By 'BAZOR_INSTALLER'
        return $false
    }

    New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
    Backup-Existing -Path $Destination

    if ([IO.Path]::GetExtension($Target) -ieq '.lnk') {
        Copy-Item -LiteralPath $Target -Destination $Destination -Force
        Write-BazorLog -What "RACCOURCI=$Destination" -Why "Reutiliser le raccourci existant pour $Description" -By 'BAZOR_INSTALLER'
        return $true
    }

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Destination)
    $extension = [IO.Path]::GetExtension($Target).ToLowerInvariant()

    if ($extension -eq '.py') {
        $pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if ($pythonw) {
            $shortcut.TargetPath = $pythonw.Source
            $shortcut.Arguments = '"{0}"' -f $Target
        } else {
            $shortcut.TargetPath = (Get-Command pyw.exe -ErrorAction SilentlyContinue).Source
            $shortcut.Arguments = '-3 "{0}"' -f $Target
        }
        $shortcut.WorkingDirectory = Split-Path -Parent $Target
    } elseif ($extension -in @('.cmd', '.bat')) {
        $shortcut.TargetPath = $env:ComSpec
        $shortcut.Arguments = '/d /k call "{0}"' -f $Target
        $shortcut.WorkingDirectory = Split-Path -Parent $Target
    } elseif ($extension -eq '.ps1') {
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File "{0}"' -f $Target
        $shortcut.WorkingDirectory = Split-Path -Parent $Target
    } elseif (Test-Path -LiteralPath $Target -PathType Container) {
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'explorer.exe'
        $shortcut.Arguments = '"{0}"' -f $Target
        $shortcut.WorkingDirectory = $Target
    } else {
        $shortcut.TargetPath = $Target
        $shortcut.WorkingDirectory = Split-Path -Parent $Target
    }

    $shortcut.Description = $Description
    $shortcut.IconLocation = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',44'
    $shortcut.Save()
    Write-BazorLog -What "RACCOURCI=$Destination" -Why "Ajouter $Description au hub BAZOR" -By 'BAZOR_INSTALLER'
    return $true
}

try {
    New-Item -ItemType Directory -Path $Root, $Hub, $Tools, $LogDir, $RunQuarantine -Force | Out-Null
    if (-not (Test-Path -LiteralPath $LogFile)) {
        New-Item -ItemType File -Path $LogFile -Force | Out-Null
    }

    Write-BazorLog -What 'DEBUT_INSTALLATION=BAZOR_HUB' -Why 'Creer un raccourci unique proposant les outils BAZOR en cours' -By 'BAZOR_INSTALLER'

    Install-ManagedFile -Name 'BAZOR_MENU_BUREAU.cmd'
    Install-ManagedFile -Name 'INSTALLER_RACCOURCI_BAZOR.cmd'
    Install-ManagedFile -Name 'INSTALLER_RACCOURCI_BAZOR.ps1'

    $desktop = Get-DesktopPath
    New-Item -ItemType Directory -Path $desktop -Force | Out-Null
    $desktopLink = Join-Path $desktop 'BAZOR.lnk'
    $menuTarget = Join-Path $Hub 'BAZOR_MENU_BUREAU.cmd'
    [void](New-BazorLink -Destination $desktopLink -Target $menuTarget -Description 'BAZOR - menu central des outils')

    $items = @(
        @{ Name = 'BAZOR AI ROOM'; Candidates = @(
            'C:\Users\vgour\AppData\Local\BazorAIROOM\DEMARRER_BAZOR_AI_ROOM.cmd',
            'C:\BAZOR TOOL\AI ROOM\LANCER_BAZOR_AI_ROOM.cmd',
            'C:\BAZOR TOOL\AI_ROOM\LANCER_BAZOR_AI_ROOM.cmd',
            'C:\BAZOR TOOL\AI ROOM\START_BAZOR_AI_ROOM.cmd',
            'C:\BAZOR TOOL\AI ROOM\run.cmd',
            'C:\Users\vgour\AppData\Local\BazorAIROOM\run.cmd'
        ) }
        @{ Name = 'AI Simple Studio BAZOR'; Candidates = @(
            'C:\Users\vgour\OneDrive\Desktop\AI Simple Studio BAZOR 2.2.lnk',
            (Join-Path $env:USERPROFILE 'Desktop\AI Simple Studio BAZOR 2.2.lnk'),
            'C:\AI\SimpleStudioV2\LANCER_BAZOR_STUDIO.cmd',
            'C:\AI\SimpleStudioV2\START_BAZOR_STUDIO.cmd',
            'C:\AI\SimpleStudioV2\LANCER_AI_SIMPLE_STUDIO.cmd',
            'C:\AI\SimpleStudioV2\start.cmd',
            'C:\AI\SimpleStudioV2\start.bat',
            'C:\AI\SimpleStudioV2'
        ) }
        @{ Name = 'ComfyUI GPU'; Candidates = @(
            'C:\AI\ComfyUI\ComfyUI_windows_portable\run_nvidia_gpu.bat'
        ) }
        @{ Name = 'BAZOR Autopilot V5'; Candidates = @(
            'C:\BAZOR TOOL\Autopilot\LANCER_AUTOPILOT_V5.cmd',
            'C:\BAZOR TOOL\Autopilot\START_AUTOPILOT_V5.cmd',
            'C:\BAZOR TOOL\Autopilot\AUTOPILOT_V5.cmd',
            'C:\BAZOR TOOL\Autopilot\AUTOPILOT.cmd',
            'C:\BAZOR TOOL\Autopilot\START_V5.cmd'
        ) }
        @{ Name = 'BAZOR PC Cleaner Ultimate'; Candidates = @(
            (Join-Path (Get-DesktopPath) 'BAZOR_CLEANER.cmd')
        ) }

        @{ Name = 'BAZOR TOR Model Scout'; Candidates = @(
            'C:\BAZOR TOOL\TorModelScout\LANCER_BAZOR_TOR_MODEL_SCOUT.cmd',
            'C:\BAZOR TOOL\TOR\LANCER_TOR.cmd',
            'C:\BAZOR TOOL\TOR\LANCER_BAZOR_TOR_MODEL_SCOUT.cmd'
        ) }
        @{ Name = 'Wii AI Relay'; Candidates = @(
            'C:\projetWII\Wii_AI_Bridge\START_BRIDGE.cmd',
            'C:\projetWII\Wii_AI_Bridge\start_bridge.ps1'
        ) }
        @{ Name = 'BAZOR Core'; Candidates = @(
            'C:\BAZOR TOOL\Core\DEMARRER_BAZOR_CORE.cmd',
            'C:\BAZOR TOOL\BAZOR CORE\DEMARRER_BAZOR_CORE.cmd',
            'C:\BAZOR TOOL\BAZOR_CORE\DEMARRER_BAZOR_CORE.cmd'
        ) }
        @{ Name = 'BAZOR Organizer'; Candidates = @(
            'C:\BAZOR TOOL\Systeme\Organisation\BAZOR Organizer\BazorOrganizer.exe',
            (Join-Path $Root "$SystemeAccent\Organisation\BAZOR Organizer\BazorOrganizer.exe")
        ) }

    )

    foreach ($item in $items) {
        $target = Get-FirstExisting -Candidates $item.Candidates
        $destination = Join-Path $Tools ($item.Name + '.lnk')
        [void](New-BazorLink -Destination $destination -Target $target -Description $item.Name)
    }

    $extractor = Get-ExtractorCandidate
    [void](New-BazorLink -Destination (Join-Path $Tools 'ChatGPT Extractor.lnk') -Target $extractor -Description 'ChatGPT Extractor')
    [void](New-BazorLink -Destination (Join-Path $Tools 'Ouvrir BAZOR Hub.lnk') -Target $Hub -Description 'Ouvrir le hub BAZOR')
    [void](New-BazorLink -Destination (Join-Path $Tools 'Ouvrir BAZOR Logs.lnk') -Target $LogDir -Description 'Ouvrir les journaux BAZOR')
    [void](New-BazorLink -Destination (Join-Path $Tools 'Ouvrir BAZOR Quarantaine.lnk') -Target $Quarantine -Description 'Ouvrir la quarantaine BAZOR')

    $inventory = Join-Path $Hub 'BAZOR_HUB_INVENTAIRE.txt'
    $inventoryLines = @(
        'BAZOR HUB - INVENTAIRE DU ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),
        '',
        'Raccourci Bureau : ' + $desktopLink,
        'Menu central     : ' + $menuTarget,
        'Raccourcis outils: ' + $Tools,
        'Journaux         : ' + $LogFile,
        'Quarantaine      : ' + $Quarantine,
        '',
        'Les elements absents ne sont pas inventes et ne generent pas de raccourci casse.',
        'Les versions precedentes sont conservees dans la quarantaine.'
    )
    Backup-Existing -Path $inventory
    Set-Content -LiteralPath $inventory -Value $inventoryLines -Encoding UTF8
    Write-BazorLog -What "INVENTAIRE=$inventory" -Why 'Laisser une trace lisible des chemins utilises' -By 'BAZOR_INSTALLER'
    Write-BazorLog -What 'FIN_INSTALLATION=BAZOR_HUB' -Why 'Hub central pret a etre ouvert depuis le Bureau' -By 'BAZOR_INSTALLER'

    Write-Host '[OK] Hub installe : ' $Hub -ForegroundColor Cyan
    Write-Host '[OK] Raccourci Bureau : ' $desktopLink -ForegroundColor Green
    Write-Host '[OK] Dossier outils : ' $Tools -ForegroundColor Green
    Write-Host '[OK] Journal : ' $LogFile -ForegroundColor DarkGray
    exit 0
} catch {
    try {
        if (Test-Path -LiteralPath $LogFile) {
            Write-BazorLog -What ('BLOCAGE=' + $_.Exception.Message) -Why 'Conserver la fenetre ouverte et tracer la cause exacte' -By 'BAZOR_INSTALLER'
        }
    } catch { }
    Write-Host '[BLOCAGE] ' $_.Exception.Message -ForegroundColor Red
    exit 1
}
