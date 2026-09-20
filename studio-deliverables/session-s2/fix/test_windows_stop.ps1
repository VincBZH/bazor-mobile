$ErrorActionPreference='Stop'
$root=Join-Path $env:TEMP ('BAZOR stop tests '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $root 'logs') -Force | Out-Null
$script:scenario='';$script:stops=@()
# All system interactions are mocked. No real process is stopped and no UAC
# prompt is approved by this suite.
function Invoke-RestMethod {
  param($Uri,$TimeoutSec)
  if($script:scenario -eq 'network'){throw 'Unavailable'}
  if($Uri.EndsWith('/api/ping')){
    return [pscustomobject]@{app= $(if($script:scenario -eq 'wrong_app'){'other'}else{'ai-simple-studio-v2'});pid=$(if($script:scenario -eq 'wrong_pid'){222}else{111});install_root=$(if($script:scenario -eq 'wrong_root'){'C:\other'}else{$root})}
  }
  if($script:scenario -eq 'unknown_jobs'){return [pscustomobject]@{error='unknown'}}
  return [pscustomobject]@{jobs=@($(if($script:scenario -eq 'busy'){[pscustomobject]@{status='running'}}))}
}
function Get-CimInstance {param($ClassName,$Filter) return [pscustomobject]@{Name=$(if($script:scenario -eq 'wrong_process'){'notepad.exe'}else{'python.exe'})}}
function Get-NetTCPConnection {param($LocalPort,$State,$ErrorAction) return [pscustomobject]@{OwningProcess=$(if($script:scenario -eq 'wrong_listener'){222}else{111})}}
function Stop-Process {param($Id,$ErrorAction) if($script:scenario -eq 'denied'){throw [System.UnauthorizedAccessException]::new('Denied')};$script:stops+= $Id}
try {
  foreach($file in @('installer.ps1','stop_studio_elevated.ps1')){
    $tokens=$null;$errors=$null
    [void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $file),[ref]$tokens,[ref]$errors)
    if($errors.Count){throw ($errors | Out-String)}
  }
  foreach($case in @('success','wrong_app','wrong_pid','wrong_root','unknown_jobs','busy','wrong_process','wrong_listener','network','denied')){
    $script:scenario=$case;$script:stops=@();$global:LASTEXITCODE=99
    & (Join-Path $PSScriptRoot 'stop_studio_elevated.ps1') -StudioRoot $root -ExpectedPid 111
    $expected=if($case -eq 'success'){0}else{1}
    if($LASTEXITCODE -ne $expected){throw ('Unexpected exit for '+$case+': '+$LASTEXITCODE)}
    if($case -eq 'success'){
      if($script:stops.Count -ne 1 -or $script:stops[0] -ne 111){throw 'Wrong stop target'}
    }elseif($script:stops.Count){throw ('Unsafe stop for '+$case)}
    Write-Output ('PASS '+$case)
  }
  Write-Output 'PASS 10 Windows stop scenarios; UAC and real GPU remain untested.'
  $global:LASTEXITCODE=0
} finally {Remove-Item -LiteralPath $root -Recurse -Force}
