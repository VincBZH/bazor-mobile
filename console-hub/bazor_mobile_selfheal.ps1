param(
  [string]$Root = "$env:USERPROFILE\bazor-mobile",
  [switch]$OpenPhone
)

$ErrorActionPreference = "SilentlyContinue"
$dataDir = Join-Path $Root "pc-relay\BAZOR_DATA"
$logDir = Join-Path $dataDir "HUB_LOGS"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "mobile_selfheal.log"
$statusFile = Join-Path $dataDir "mobile_selfheal_status.json"

function Log([string]$Text) {
  Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),$Text) -Encoding UTF8
}

function Test-Url([string]$Url,[int]$TimeoutSec=1) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSec
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Find-Python {
  $p = Get-Command pythonw.exe -ErrorAction SilentlyContinue
  if($p){ return $p.Source }
  $p = Get-Command python.exe -ErrorAction SilentlyContinue
  if($p){ return $p.Source }
  return $null
}

function Wait-Url([string]$Url,[int]$Seconds=12) {
  $end = (Get-Date).AddSeconds($Seconds)
  while((Get-Date) -lt $end) {
    if(Test-Url $Url 1){ return $true }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

$coreUrl = "http://127.0.0.1:8775/api/v1/security/status"
$webUrl  = "http://127.0.0.1:8776/index.html"
$py = Find-Python

Log "=== BAZOR MOBILE SELFHEAL ==="

# Laisse d'abord le Hub central lancer silencieusement ses services.
$coreOk = Wait-Url $coreUrl 8
$webOk = Wait-Url $webUrl 3

if(-not $coreOk -and $py) {
  $core = Join-Path $Root "pc-relay\bazor_pc_relay_v3.py"
  if(Test-Path $core) {
    Log "Core 8775 absent : relance de secours."
    $env:BAZOR_MOBILE_PORT = "8775"
    $out = Join-Path $logDir "core_selfheal_stdout.log"
    $err = Join-Path $logDir "core_selfheal_stderr.log"
    Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList @($core) -WorkingDirectory (Split-Path $core) -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $coreOk = Wait-Url $coreUrl 12
  }
}

if(-not $webOk -and $py) {
  Log "Gateway 8776 absent : relance du vrai Gateway BAZOR."
  $gateway = Join-Path $Root "console-hub\bazor_mobile_gateway.py"
  $out = Join-Path $logDir "web_selfheal_stdout.log"
  $err = Join-Path $logDir "web_selfheal_stderr.log"
  if(Test-Path $gateway) {
    Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList @($gateway) -WorkingDirectory $Root -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $webOk = Wait-Url $webUrl 8
  } else {
    Log "Gateway introuvable : aucun serveur de remplacement non-API n'est lance."
  }
}

$usbOk = $false
$usb = Join-Path $Root "console-hub\bazor_usb_android_bridge.ps1"
if(Test-Path $usb) {
  Log "Réapplication du pont USB 8775/8776 après démarrage des services."
  if($OpenPhone) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $usb -Root $Root -OpenPhone
  } else {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $usb -Root $Root
  }
  $usbOk = ($LASTEXITCODE -eq 0)
}

@{
  ok = [bool]($coreOk -and $webOk -and $usbOk)
  core = [bool]$coreOk
  web = [bool]$webOk
  usb = [bool]$usbOk
  core_url = $coreUrl
  web_url = $webUrl
  time = (Get-Date).ToString("o")
} | ConvertTo-Json -Depth 4 | Set-Content -Path $statusFile -Encoding UTF8

Log ("Résultat core={0} web={1} usb={2}" -f $coreOk,$webOk,$usbOk)
exit $(if($coreOk -and $webOk -and $usbOk){0}else{5})
