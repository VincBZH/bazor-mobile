param(
  [string]$Root = "$env:USERPROFILE\bazor-mobile"
)
$ErrorActionPreference="SilentlyContinue"

$dataDir=Join-Path $Root "pc-relay\BAZOR_DATA"
$logDir=Join-Path $dataDir "HUB_LOGS"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log=Join-Path $logDir "mobile_network_repair.log"
$statusFile=Join-Path $dataDir "mobile_network_status.json"
$urlFile=Join-Path $dataDir "mobile_url.txt"

function Log([string]$t){
  Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),$t) -Encoding UTF8
}
function IsPrivateIPv4([string]$ip){
  return ($ip -match '^10\.' -or $ip -match '^192\.168\.' -or $ip -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.')
}

Log "=== REPAIR MOBILE NETWORK ==="

# Pare-feu BAZOR : LAN uniquement.
netsh advfirewall firewall delete rule name="BAZOR Mobile Core 8775" *> $null
netsh advfirewall firewall add rule name="BAZOR Mobile Core 8775" dir=in action=allow protocol=TCP localport=8775 profile=any remoteip=localsubnet *> $null
netsh advfirewall firewall delete rule name="BAZOR Mobile Web 8776" *> $null
netsh advfirewall firewall add rule name="BAZOR Mobile Web 8776" dir=in action=allow protocol=TCP localport=8776 profile=any remoteip=localsubnet *> $null

# Choisir en priorité une vraie interface LAN avec passerelle.
$adapters = Get-NetIPConfiguration | Where-Object {
  $_.IPv4Address -and $_.NetAdapter.Status -eq 'Up'
}

$candidates=@()
foreach($a in $adapters){
  $name=[string]$a.InterfaceAlias
  $desc=[string]$a.NetAdapter.InterfaceDescription
  $virtual = ($name -match '(?i)vpn|wireguard|wintun|tap|tailscale|zerotier|hyper-v|vethernet|docker|wsl|loopback') -or
             ($desc -match '(?i)vpn|wireguard|wintun|tap|tailscale|zerotier|hyper-v|virtual|docker|wsl')
  foreach($addr in @($a.IPv4Address)){
    $ip=[string]$addr.IPAddress
    if(-not (IsPrivateIPv4 $ip)){ continue }
    $gw=""
    if($a.IPv4DefaultGateway){ $gw=[string]$a.IPv4DefaultGateway.NextHop }
    $score=0
    if($gw){$score+=100}
    if(-not $virtual){$score+=50}
    if($ip -like '192.168.*'){$score+=20}
    elseif($ip -like '10.*'){$score+=10}
    $candidates += [pscustomobject]@{
      IP=$ip; Adapter=$name; Description=$desc; Gateway=$gw; Virtual=$virtual; Score=$score
    }
  }
}

$chosen=$candidates | Sort-Object Score -Descending | Select-Object -First 1
$ip=$null
if($chosen){$ip=$chosen.IP}

$webListen = @(Get-NetTCPConnection -State Listen -LocalPort 8776)
$coreListen = @(Get-NetTCPConnection -State Listen -LocalPort 8775)
$webBoundAll = @($webListen | Where-Object { $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::' }).Count -gt 0
$coreBoundAll = @($coreListen | Where-Object { $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::' }).Count -gt 0

$webSelf=$false
$coreSelf=$false
$url=""
if($ip){
  $url="http://" + $ip + ":8776/"
  Set-Content -Path $urlFile -Value $url -Encoding UTF8
  try {
    $r=Invoke-WebRequest -UseBasicParsing -Uri ($url+"index.html?lancheck="+[DateTimeOffset]::Now.ToUnixTimeSeconds()) -TimeoutSec 3
    $webSelf=($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
  } catch {}
  try {
    $r=Invoke-WebRequest -UseBasicParsing -Uri ("http://" + $ip + ":8775/api/v1/security/status") -TimeoutSec 3
    $coreSelf=($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
  } catch {}
  Log ("Selected LAN IP={0} Adapter={1} Gateway={2} Virtual={3}" -f $ip,$chosen.Adapter,$chosen.Gateway,$chosen.Virtual)
  Log ("Web listen_all={0} self_test={1}; Core listen_all={2} self_test={3}" -f $webBoundAll,$webSelf,$coreBoundAll,$coreSelf)
}else{
  Remove-Item -Force $urlFile -ErrorAction SilentlyContinue
  Log "No usable private LAN IPv4 detected"
}

$status=[ordered]@{
  time=(Get-Date).ToString("s")
  ip=$ip
  url=$url
  adapter=if($chosen){$chosen.Adapter}else{$null}
  gateway=if($chosen){$chosen.Gateway}else{$null}
  virtual=if($chosen){[bool]$chosen.Virtual}else{$null}
  web_listen_all=[bool]$webBoundAll
  core_listen_all=[bool]$coreBoundAll
  web_self_test=[bool]$webSelf
  core_self_test=[bool]$coreSelf
  candidates=@($candidates | Sort-Object Score -Descending)
}
$status | ConvertTo-Json -Depth 5 | Set-Content -Path $statusFile -Encoding UTF8
exit 0
