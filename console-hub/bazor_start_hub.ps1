param(
  [string]$Root = "$env:USERPROFILE\bazor-mobile"
)

$ErrorActionPreference = "Stop"

function Resolve-BazorPython {
  $patterns = 'bazor_console_hub\.py|bazor_pc_relay_v3\.py|bazor_mobile_gateway\.py|bazor_github_watcher\.py'
  try {
    $running = Get-CimInstance Win32_Process |
      Where-Object { [string]$_.CommandLine -match $patterns } |
      Where-Object { $_.ExecutablePath -and (Test-Path $_.ExecutablePath) } |
      Select-Object -First 1
    if ($running) {
      return [pscustomobject]@{ Path = [string]$running.ExecutablePath; Prefix = @() }
    }
  } catch {}

  foreach ($name in @('pythonw.exe','python.exe')) {
    try {
      $cmd = Get-Command $name -ErrorAction Stop
      if ($cmd.Source -and (Test-Path $cmd.Source)) {
        return [pscustomobject]@{ Path = [string]$cmd.Source; Prefix = @() }
      }
    } catch {}
  }

  try {
    $py = Get-Command 'py.exe' -ErrorAction Stop
    if ($py.Source -and (Test-Path $py.Source)) {
      return [pscustomobject]@{ Path = [string]$py.Source; Prefix = @('-3') }
    }
  } catch {}

  $pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
  $bases = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
    (Join-Path $env:ProgramFiles 'Python'),
    $(if ($pf86) { Join-Path $pf86 'Python' } else { $null })
  ) | Where-Object { $_ -and (Test-Path $_) }

  foreach ($base in $bases) {
    foreach ($exeName in @('pythonw.exe','python.exe')) {
      try {
        $found = Get-ChildItem -Path $base -Filter $exeName -File -Recurse -ErrorAction SilentlyContinue |
          Sort-Object FullName -Descending |
          Select-Object -First 1
        if ($found) {
          return [pscustomobject]@{ Path = [string]$found.FullName; Prefix = @() }
        }
      } catch {}
    }
  }

  return $null
}

if (-not (Test-Path $Root)) {
  throw "Dossier BAZOR absent: $Root"
}

$hub = Join-Path $Root 'console-hub\bazor_console_hub.py'
$review = Join-Path $Root 'console-hub\bazor_hub_expert_review.py'
$guard = Join-Path $Root 'console-hub\bazor_popup_guard.py'

if (-not (Test-Path $hub)) {
  throw "Hub absent: $hub"
}

$py = Resolve-BazorPython
if (-not $py) {
  throw "Python BAZOR introuvable. Aucun processus BAZOR Python, python/pythonw/py ni installation standard detectee."
}

$pythonPath = $py.Path
$prefix = @($py.Prefix)

$guiPython = $pythonPath
if ([IO.Path]::GetFileName($pythonPath) -ieq 'python.exe') {
  $candidate = Join-Path ([IO.Path]::GetDirectoryName($pythonPath)) 'pythonw.exe'
  if (Test-Path $candidate) { $guiPython = $candidate }
}

function Start-PyHidden([string]$Exe,[string[]]$Prefix,[string]$Script,[string[]]$Extra=@()) {
  $args = @()
  $args += $Prefix
  $args += $Script
  $args += $Extra
  Start-Process -FilePath $Exe -ArgumentList $args -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
}

if (Test-Path $review) {
  Start-PyHidden -Exe $pythonPath -Prefix $prefix -Script $review
}
if (Test-Path $guard) {
  Start-PyHidden -Exe $pythonPath -Prefix $prefix -Script $guard
}

$args = @()
$args += $prefix
$args += $hub
$args += '--centralize'
Start-Process -FilePath $guiPython -ArgumentList $args -WorkingDirectory $Root | Out-Null

Write-Output ("[OK] Hub BAZOR lance avec: " + $guiPython)
exit 0
