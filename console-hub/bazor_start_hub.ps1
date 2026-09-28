param(
  [string]$Root = "$env:USERPROFILE\bazor-mobile"
)

$ErrorActionPreference = "Stop"

# Session zero-cost: child BAZOR processes started by this launcher cannot use paid providers.
$env:BAZOR_EXTERNAL_BUDGET = "0"
$env:BAZOR_MAMMOUTH_BUDGET_USD = "0"
$env:BAZOR_NOTRACK_ENABLED = "0"
$env:MAMMOUTH_API_KEY = ""
$env:NOTRACK_API_KEY = ""
$env:OPENAI_API_KEY = ""

function Test-LocalHttp([string]$Url,[int]$TimeoutSec=2) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSec
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300)
  } catch { return $false }
}

function Start-BazorRoomSafe {
  if (Test-LocalHttp 'http://127.0.0.1:8765/api/status' 1) {
    return 'ALREADY_RUNNING'
  }
  if (Test-LocalHttp 'http://127.0.0.1:8765/' 1) {
    return 'ALREADY_RUNNING'
  }

  $roomRoot = Join-Path $env:LOCALAPPDATA 'BazorAIROOM'
  if (-not (Test-Path $roomRoot)) { return 'ROOM_ROOT_MISSING' }

  $cmdCandidates = @(
    'LANCER_BAZOR_AI_ROOM.cmd','LANCER_AI_ROOM.cmd','Lancer.cmd','start.cmd'
  )
  foreach ($name in $cmdCandidates) {
    $p = Join-Path $roomRoot $name
    if (Test-Path $p) {
      Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c',('"' + $p + '"')) -WorkingDirectory $roomRoot -WindowStyle Hidden | Out-Null
      for ($i=0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        if ((Test-LocalHttp 'http://127.0.0.1:8765/api/status' 1) -or
            (Test-LocalHttp 'http://127.0.0.1:8765/' 1)) { return 'STARTED' }
      }
      return 'START_TIMEOUT'
    }
  }

  foreach ($name in @('app.py','main.py','server.py')) {
    $p = Join-Path $roomRoot $name
    if (Test-Path $p) {
      $pyRoom = Resolve-BazorPython
      if (-not $pyRoom) { return 'PYTHON_MISSING' }
      $args = @(); $args += @($pyRoom.Prefix); $args += $p
      Start-Process -FilePath $pyRoom.Path -ArgumentList $args -WorkingDirectory $roomRoot -WindowStyle Hidden | Out-Null
      for ($i=0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        if ((Test-LocalHttp 'http://127.0.0.1:8765/api/status' 1) -or
            (Test-LocalHttp 'http://127.0.0.1:8765/' 1)) { return 'STARTED' }
      }
      return 'START_TIMEOUT'
    }
  }
  return 'NO_LAUNCHER'
}

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

# One-click recovery: the .CMD has already updated main before loading this file.
# Start the existing Room only; no deployment or file replacement is performed.
Start-Sleep -Seconds 2
$roomState = Start-BazorRoomSafe
$coreOk = (Test-LocalHttp 'http://127.0.0.1:8775/api/v1/health' 2) -or
          (Test-LocalHttp 'http://127.0.0.1:8775/api/v1/security/status' 2)
$roomOk = (Test-LocalHttp 'http://127.0.0.1:8765/api/status' 2) -or
          (Test-LocalHttp 'http://127.0.0.1:8765/' 2)
$ollamaOk = Test-LocalHttp 'http://127.0.0.1:11434/api/tags' 2

$reportDir = Join-Path $env:LOCALAPPDATA 'BAZOR\Reports'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$public = Join-Path $reportDir 'oneclick_services_public.txt'
@(
  '[BAZOR-ONECLICK-SERVICES]',
  ('CORE_8775: ' + $(if ($coreOk) {'OK'} else {'BLOCKED'})),
  ('ROOM_8765: ' + $(if ($roomOk) {'OK'} else {'BLOCKED'})),
  ('ROOM_START: ' + $roomState),
  ('OLLAMA_11434: ' + $(if ($ollamaOk) {'OK'} else {'BLOCKED'})),
  'PAID_AI_CALLS: ZERO',
  'DEPLOYMENT: NONE'
) | Set-Content -Path $public -Encoding UTF8

try {
  $gh = Get-Command 'gh.exe' -ErrorAction Stop
  & $gh.Source auth status *> $null
  if ($LASTEXITCODE -eq 0) {
    & $gh.Source issue comment 171 --repo VincBZH/bazor-mobile --body-file $public *> $null
  }
} catch {}

Write-Output ('[BAZOR] Room=' + $roomState + ' Core=' + $coreOk + ' Ollama=' + $ollamaOk)
exit 0
