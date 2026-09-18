param(
  [string]$Root = "$env:USERPROFILE\bazor-mobile",
  [switch]$OpenPhone
)

$ErrorActionPreference = "SilentlyContinue"
$logDir = Join-Path $Root "pc-relay\BAZOR_DATA\HUB_LOGS"
$dataDir = Join-Path $Root "pc-relay\BAZOR_DATA"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "usb_android_bridge.log"
$statusFile = Join-Path $dataDir "usb_android_status.json"

function Log([string]$Text) {
  Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),$Text) -Encoding UTF8
}

function SaveStatus($obj) {
  $obj | ConvertTo-Json -Depth 5 | Set-Content -Path $statusFile -Encoding UTF8
}

function Find-Adb {
  $candidates = @()
  $cmd = Get-Command adb.exe -ErrorAction SilentlyContinue
  if($cmd){ $candidates += $cmd.Source }
  if($env:LOCALAPPDATA){
    $candidates += (Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe")
  }
  if($env:ANDROID_HOME){ $candidates += (Join-Path $env:ANDROID_HOME "platform-tools\adb.exe") }
  if($env:ANDROID_SDK_ROOT){ $candidates += (Join-Path $env:ANDROID_SDK_ROOT "platform-tools\adb.exe") }
  foreach($p in $candidates | Select-Object -Unique){
    if(Test-Path $p){ return $p }
  }
  return $null
}

$adb = Find-Adb
if(-not $adb){
  Log "ADB introuvable - installation officielle Google Platform Tools..."
  try {
    $toolsRoot = Join-Path $env:LOCALAPPDATA "BAZOR\Android"
    $zip = Join-Path $toolsRoot "platform-tools-latest-windows.zip"
    $dest = Join-Path $toolsRoot "platform-tools"
    New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -OutFile $zip
    if(Test-Path $dest){ Remove-Item -Recurse -Force $dest }
    Expand-Archive -Path $zip -DestinationPath $toolsRoot -Force
    Remove-Item -Force $zip
    $candidate = Join-Path $dest "adb.exe"
    if(Test-Path $candidate){
      $adb = $candidate
      Log ("ADB installé: " + $adb)
    }
  } catch {
    Log ("Installation ADB échec: " + $_.Exception.Message)
  }
}

if(-not $adb){
  Log "ADB indisponible"
  SaveStatus @{
    ok=$false; connected=$false; reason="adb_missing"; url="http://127.0.0.1:8776/"; time=(Get-Date).ToString("o")
  }
  exit 2
}

Log ("ADB=" + $adb)
& $adb start-server *> $null

$devices = & $adb devices
$lines = @($devices | Select-Object -Skip 1 | Where-Object { $_ -match "\S+\s+device$" })
if($lines.Count -lt 1){
  $unauth = @($devices | Select-Object -Skip 1 | Where-Object { $_ -match "\S+\s+unauthorized$" })
  $reason = if($unauth.Count){ "unauthorized" } else { "device_missing" }
  Log ("Téléphone non prêt: " + $reason)
  SaveStatus @{
    ok=$false; connected=$false; reason=$reason; adb=$adb; url="http://127.0.0.1:8776/"; time=(Get-Date).ToString("o")
  }
  exit 3
}

$serial = ($lines[0] -split "\s+")[0]
Log ("DEVICE=" + $serial)

& $adb -s $serial reverse --remove tcp:8775 *> $null
& $adb -s $serial reverse --remove tcp:8776 *> $null
& $adb -s $serial reverse tcp:8775 tcp:8775 *> $null
$coreRc = $LASTEXITCODE
& $adb -s $serial reverse tcp:8776 tcp:8776 *> $null
$webRc = $LASTEXITCODE

$reverse = & $adb -s $serial reverse --list
$ok = ($coreRc -eq 0 -and $webRc -eq 0 -and ($reverse -match "tcp:8775") -and ($reverse -match "tcp:8776"))
$url = "http://127.0.0.1:8776/"

SaveStatus @{
  ok=[bool]$ok
  connected=$true
  serial=$serial
  adb=$adb
  core_reverse=($reverse -match "tcp:8775")
  web_reverse=($reverse -match "tcp:8776")
  url=$url
  biometric_localhost=$true
  time=(Get-Date).ToString("o")
}

if($ok){
  Set-Content -Path (Join-Path $dataDir "mobile_url.txt") -Value $url -Encoding UTF8
  Log "USB reverse OK 8775/8776"
  if($OpenPhone){
    & $adb -s $serial shell am start -a android.intent.action.VIEW -d $url *> $null
    Log "URL ouverte sur le téléphone"
  }
  exit 0
}

Log ("USB reverse échec: " + ($reverse -join " | "))
exit 4
