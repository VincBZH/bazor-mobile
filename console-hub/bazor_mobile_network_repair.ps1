param(
  [string]$Root = "$env:USERPROFILE\bazor-mobile"
)
$ErrorActionPreference="SilentlyContinue"
$logDir=Join-Path $Root "pc-relay\BAZOR_DATA\HUB_LOGS"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log=Join-Path $logDir "mobile_network_repair.log"
function Log([string]$t){Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),$t) -Encoding UTF8}

Log "=== REPAIR MOBILE NETWORK ==="
netsh advfirewall firewall delete rule name="BAZOR Mobile Core 8775" *> $null
netsh advfirewall firewall add rule name="BAZOR Mobile Core 8775" dir=in action=allow protocol=TCP localport=8775 profile=any remoteip=localsubnet *> $null
netsh advfirewall firewall delete rule name="BAZOR Mobile Web 8776" *> $null
netsh advfirewall firewall add rule name="BAZOR Mobile Web 8776" dir=in action=allow protocol=TCP localport=8776 profile=any remoteip=localsubnet *> $null

$ips = Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {
    $_.IPAddress -notlike '127.*' -and
    $_.IPAddress -notlike '169.254.*' -and
    $_.AddressState -eq 'Preferred'
  } |
  Sort-Object InterfaceMetric

$ip=$null
foreach($x in $ips){
  if($x.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)'){
    $ip=$x.IPAddress
    break
  }
}
if(-not $ip -and $ips){$ip=$ips[0].IPAddress}

if($ip){
  $url="http://" + $ip + ":8776/"
  Set-Content -Path (Join-Path $Root "pc-relay\BAZOR_DATA\mobile_url.txt") -Value $url -Encoding UTF8
  Log ("URL=" + $url)
}else{
  Log "No LAN IPv4 detected"
}
exit 0
