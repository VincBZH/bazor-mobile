param([Parameter(Mandatory=$true)][string]$StudioRoot,[Parameter(Mandatory=$true)][int]$ExpectedPid)
# This helper only stops a freshly verified Studio process. It never installs
# files, starts servers or accepts arbitrary shell commands.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($StudioRoot).TrimEnd('\')
$log=Join-Path $root 'logs\session-s2-elevated-stop.log'
function Audit([string]$message){
  Add-Content -LiteralPath $log -Encoding UTF8 -Value ('['+[DateTime]::UtcNow.ToString('o')+'] BAZOR S2.2 stop-only | '+$message)
}
try {
  if($ExpectedPid -le 0){throw 'PID invalide.'}
  $runtime=Invoke-RestMethod -Uri 'http://127.0.0.1:8191/api/ping' -TimeoutSec 5
  if($runtime.app -ne 'ai-simple-studio-v2' -or [int]$runtime.pid -ne $ExpectedPid -or [IO.Path]::GetFullPath($runtime.install_root).TrimEnd('\') -ine $root){throw 'Identite Studio changee : aucun arret.'}
  $jobs=Invoke-RestMethod -Uri 'http://127.0.0.1:8191/api/jobs' -TimeoutSec 5
  if($null -eq $jobs -or $null -eq $jobs.PSObject.Properties['jobs']){throw 'Liste des taches non verifiable.'}
  if(@($jobs.jobs | Where-Object {$_.status -in @('queued','running','submitting','uncertain')}).Count){throw 'Generation active : aucun arret.'}
  $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ExpectedPid)
  if(!$process -or $process.Name -notmatch '^python(w)?\.exe$'){throw 'Processus Python non confirme.'}
  $listeners=@(Get-NetTCPConnection -LocalPort 8191 -State Listen -ErrorAction Stop)
  if($listeners.OwningProcess -notcontains $ExpectedPid){throw 'PID different du service sur 8191.'}
  Audit ('Arret PID '+$ExpectedPid+' ; raison=acces refuse au lanceur utilisateur ; installation='+$root+' ; ComfyUI preserve')
  Stop-Process -Id $ExpectedPid -ErrorAction Stop
  Audit ('Arret confirme PID '+$ExpectedPid)
  exit 0
} catch {
  try {Audit ('ARRET REFUSE : '+$_.Exception.Message)} catch {}
  Write-Host 'Arret non effectue. Consulter le journal session-s2-elevated-stop.log.'
  exit 1
}
