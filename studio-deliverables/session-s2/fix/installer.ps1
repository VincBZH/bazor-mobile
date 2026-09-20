param([string]$StudioRoot='C:\AI\SimpleStudioV2')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$root=[IO.Path]::GetFullPath($StudioRoot).TrimEnd('\')
$portable='C:\AI\ComfyUI\ComfyUI_windows_portable'
$python=Join-Path $portable 'python_embeded\python.exe'
$logDir=Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$installLog=Join-Path $logDir 'session-s2-installer.log'
function Log([string]$message){$line='['+[DateTime]::UtcNow.ToString('o')+'] '+$message;Write-Host $line;Add-Content -LiteralPath $installLog -Value $line -Encoding UTF8}
function Probe([string]$url){try{return Invoke-RestMethod -Uri $url -TimeoutSec 3}catch{return $null}}
function Occupied([int]$port){return @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).Count -gt 0}
function Test-AccessDenied($record){
  if($record.CategoryInfo.Category -eq 'PermissionDenied'){return $true}
  $cause=$record.Exception
  for($depth=0;$cause -and $depth -lt 8;$depth++){
    if($cause -is [System.UnauthorizedAccessException] -or $cause.NativeErrorCode -eq 5){return $true}
    $cause=$cause.InnerException
  }
  return $false
}
try{
  Log 'BAZOR STUDIO - SESSION S2.3'
  if(!(Test-Path -LiteralPath $python)){throw 'Python ComfyUI introuvable.'}
  if(!(Test-Path -LiteralPath (Join-Path $root 'app\studio.py'))){throw 'Installation Studio introuvable.'}
  Log '1/5 - Verification de compatibilite, avant modification.'
  & $python (Join-Path $PSScriptRoot 'apply_fix.py') --root $root --check
  if($LASTEXITCODE -ne 0){throw 'Version locale differente : aucun fichier modifie. Voir le diagnostic ci-dessus.'}
  $runtime=Probe 'http://127.0.0.1:8191/api/ping'
  if($runtime){
    if($runtime.app -ne 'ai-simple-studio-v2' -or [IO.Path]::GetFullPath($runtime.install_root).TrimEnd('\') -ine $root){throw 'Le port 8191 appartient a une autre installation. Elle a ete preservee.'}
    $jobs=Probe 'http://127.0.0.1:8191/api/jobs'
    if(!$jobs -or $null -eq $jobs.PSObject.Properties['jobs']){throw 'Impossible de verifier les taches actives. Studio conserve en marche.'}
    if(@($jobs.jobs | Where-Object {$_.status -in @('queued','running','submitting','uncertain')}).Count){throw 'Une generation est encore active. Relancer ce correctif une fois terminee.'}
    $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$runtime.pid)
    if(!$process -or $process.Name -notmatch '^python(w)?\.exe$'){throw 'Processus Studio non identifiable. Aucun processus arrete.'}
    # PID, HTTP application identity and install_root must all agree.
    $listeners=@(Get-NetTCPConnection -LocalPort 8191 -State Listen -ErrorAction Stop)
    if($listeners.OwningProcess -notcontains [int]$runtime.pid){throw 'Identite du processus Studio incoherente.'}
    Log ('2/5 - Arret du seul Studio identifie, PID '+$runtime.pid+'. ComfyUI conserve.')
    try {
      Stop-Process -Id ([int]$runtime.pid) -ErrorAction Stop
    } catch {
      $denied=Test-AccessDenied $_
      if(!$denied){throw}
      Log 'Windows refuse cet arret sans elevation. Autorise la demande Windows pour arreter uniquement ce Studio.'
      $helper=Join-Path $PSScriptRoot 'stop_studio_elevated.ps1'
      $argsUac=@('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$helper+'"'),'-StudioRoot',('"'+$root+'"'),'-ExpectedPid',([string][int]$runtime.pid))
      try {$stopper=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -Verb RunAs -ArgumentList $argsUac -Wait -PassThru -ErrorAction Stop}
      catch {throw 'Autorisation Windows non obtenue. Installation annulee avant modification des fichiers Studio.'}
      if($stopper.ExitCode -ne 0){throw 'Arret autorise impossible ou identite changee. Aucun fichier Studio modifie. Voir session-s2-elevated-stop.log.'}
      Log 'Arret autorise termine. Installation poursuivie avec les droits utilisateur habituels.'
    }
    for($i=0;$i -lt 20 -and (Occupied 8191);$i++){Start-Sleep -Milliseconds 250}
    if(Occupied 8191){throw '8191 reste occupe apres arret. Aucun fichier Studio modifie.'}
  }elseif(Occupied 8191){throw 'Un service non identifie occupe 8191. Il a ete preserve.'}
  Log '3/5 - Sauvegarde des fichiers modifies puis installation transactionnelle.'
  & $python (Join-Path $PSScriptRoot 'apply_fix.py') --root $root
  if($LASTEXITCODE -ne 0){throw 'Installation interrompue. La sauvegarde permet le retour arriere.'}
  Log '4/5 - Connexion a ComfyUI.'
  if(!(Probe 'http://127.0.0.1:8188/system_stats')){
    if(Occupied 8188){throw '8188 occupe mais ComfyUI ne repond pas. Aucun second moteur lance.'}
    $main=Join-Path $portable 'ComfyUI\main.py'
    if(!(Test-Path -LiteralPath $main)){throw 'ComfyUI main.py introuvable.'}
    $stamp=Get-Date -Format yyyyMMdd_HHmmss
    Start-Process -FilePath $python -ArgumentList @('-s',('"'+$main+'"'),'--windows-standalone-build','--listen','127.0.0.1','--port','8188') -WorkingDirectory $portable -RedirectStandardOutput (Join-Path $logDir ('comfy-s2-'+$stamp+'.log')) -RedirectStandardError (Join-Path $logDir ('comfy-s2-'+$stamp+'.err.log')) | Out-Null
    $ready=$false
    for($i=0;$i -lt 60;$i++){if(Probe 'http://127.0.0.1:8188/system_stats'){$ready=$true;break};Start-Sleep -Seconds 2}
    if(!$ready){throw 'ComfyUI ne repond pas encore. Consulte le journal comfy-s2.'}
  }
  Log '5/5 - Demarrage et verification HTTP de la version installee.'
  $script=Join-Path $root 'app\studio.py'
  $stamp=Get-Date -Format yyyyMMdd_HHmmss
  $server=Start-Process -FilePath $python -ArgumentList @(('"'+$script+'"'),'--port','8191') -WorkingDirectory (Join-Path $root 'app') -RedirectStandardOutput (Join-Path $logDir ('studio-s2-'+$stamp+'.log')) -RedirectStandardError (Join-Path $logDir ('studio-s2-'+$stamp+'.err.log')) -PassThru
  $ready=$false
  for($i=0;$i -lt 30;$i++){
    $reply=Probe 'http://127.0.0.1:8191/api/ping'
    if($reply -and $reply.build_id -eq '3.0.5-session-s2.3' -and $reply.pid -eq $server.Id){$ready=$true;break}
    Start-Sleep -Seconds 1
  }
  if(!$ready){throw 'Le nouveau Studio ne repond pas. Consulte le journal studio-s2.'}
  $check=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8191/static/app.js?v=s2' -TimeoutSec 5
  if($check.Content -notmatch 'BAZOR_SESSION_S2'){throw 'Interface S2 non confirmee.'}
  @{verified_at=[DateTime]::UtcNow.ToString('o');http_verified=$true;generation_gpu_verified=$false;pid=$server.Id;build_id=$reply.build_id} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logDir 'session-s2-runtime.json') -Encoding UTF8
  Log 'Studio S2 repond. Le test HTTP ne certifie pas la qualite des generations GPU.'
  Start-Process 'http://127.0.0.1:8191/?session=s2'
}catch{Log ('ARRET : '+$_.Exception.Message);exit 1}
