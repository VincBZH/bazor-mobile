param(
  [string]$Root = "$env:USERPROFILE\bazor-mobile"
)

$ErrorActionPreference = "SilentlyContinue"
$logDir = Join-Path $Root "pc-relay\BAZOR_DATA\HUB_LOGS"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "clean_start.log"

function Log([string]$Text) {
  $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Text"
  Add-Content -Path $log -Value $line -Encoding UTF8
}

Log "=== BAZOR ONE CLICK CLEAN START ==="

# 1) Stop only obsolete/current BAZOR Mobile stack processes.
# Never touch unrelated Python, CMD, ComfyUI, Studio, Wii or user applications.
$patterns = @(
  'bazor_console_hub\.py',
  'bazor_github_watcher\.py',
  'bazor_pc_relay_v3\.py',
  'http\.server\s+8776',
  'DEMARRER_GITHUB_WATCHER\.cmd',
  'bazor_popup_guard\.py'
)

# Legacy curl probes are allowed to be killed ONLY when they clearly target BAZOR.
$bazorCurlPattern = '(?i)(bazor|bazor-mobile|127\.0\.0\.1:(8775|8776|8765|8766|8188|8191)|192\.168\.\d+\.\d+:(8775|8776))'

$self = $PID
$targets = Get-CimInstance Win32_Process | Where-Object {
  $cmd = [string]$_.CommandLine
  if ($_.ProcessId -eq $self -or [string]::IsNullOrWhiteSpace($cmd)) { return $false }

  # Anciennes sondes curl BAZOR : elles provoquent des fenêtres noires répétées.
  if ($_.Name -ieq 'curl.exe' -and $cmd -match $bazorCurlPattern) {
    return $true
  }

  foreach ($p in $patterns) {
    if ($cmd -match $p) { return $true }
  }
  return $false
}

$ids = @($targets | Select-Object -ExpandProperty ProcessId -Unique)
foreach ($id in $ids) {
  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id"
  if ($p) {
    Log ("STOP PID {0} {1} :: {2}" -f $id,$p.Name,$p.CommandLine)
    & taskkill.exe /PID $id /T /F *> $null
  }
}

# 2) Disable only legacy scheduled tasks that relaunch the old watcher
#    or run a BAZOR-specific curl probe.
$disabled = 0
Get-ScheduledTask | ForEach-Object {
  $task = $_
  $joined = (($task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " ")
  $oldWatcher = $joined -match 'DEMARRER_GITHUB_WATCHER\.cmd|bazor_github_watcher\.py'
  $oldCurl = ($joined -match '(?i)curl(\.exe)?') -and ($joined -match $bazorCurlPattern)

  if ($oldWatcher -or $oldCurl) {
    Disable-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath | Out-Null
    Log ("DISABLE TASK {0}{1} :: {2}" -f $task.TaskPath,$task.TaskName,$joined)
    $disabled++
  }
}

# 3) Remove the deferred restart marker from obsolete sessions.
$pending = Join-Path $Root "pc-relay\BAZOR_DATA\pending_core_restart.flag"
if (Test-Path $pending) {
  Remove-Item -Force $pending
  Log "Removed stale pending_core_restart.flag"
}

# 4) Give Windows a moment to release ports/process handles.
Start-Sleep -Milliseconds 900

Log ("Cleanup done. Processes stopped={0}; legacy scheduled tasks disabled={1}; BAZOR curl probes included" -f $ids.Count,$disabled)
exit 0
