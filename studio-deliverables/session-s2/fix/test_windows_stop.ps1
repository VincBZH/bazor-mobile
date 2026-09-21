$ErrorActionPreference='Stop'
$root=Join-Path $env:TEMP ('BAZOR stop tests '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $root 'logs') -Force | Out-Null
$global:BazorStopTestState=@{scenario='';stops=@()}
# All system interactions are mocked. No real process is stopped and no UAC
# prompt is approved by this suite.
function Invoke-RestMethod {
  param($Uri,$TimeoutSec)
  if($global:BazorStopTestState.scenario -eq 'network'){throw 'Unavailable'}
  if($Uri.EndsWith('/api/ping')){
    return [pscustomobject]@{app= $(if($global:BazorStopTestState.scenario -eq 'wrong_app'){'other'}else{'ai-simple-studio-v2'});pid=$(if($global:BazorStopTestState.scenario -eq 'wrong_pid'){222}else{111});install_root=$(if($global:BazorStopTestState.scenario -eq 'wrong_root'){'C:\other'}else{$root})}
  }
  if($global:BazorStopTestState.scenario -eq 'unknown_jobs'){return [pscustomobject]@{error='unknown'}}
  return [pscustomobject]@{jobs=@($(if($global:BazorStopTestState.scenario -eq 'busy'){[pscustomobject]@{status='running'}}))}
}
function Get-CimInstance {param($ClassName,$Filter) return [pscustomobject]@{Name=$(if($global:BazorStopTestState.scenario -eq 'wrong_process'){'notepad.exe'}else{'python.exe'})}}
function Get-NetTCPConnection {param($LocalPort,$State,$ErrorAction) return [pscustomobject]@{OwningProcess=$(if($global:BazorStopTestState.scenario -eq 'wrong_listener'){222}else{111})}}
function Stop-Process {param($Id,$ErrorAction) if($global:BazorStopTestState.scenario -eq 'denied'){throw [System.UnauthorizedAccessException]::new('Denied')};$global:BazorStopTestState.stops+= $Id}
try {
  foreach($file in @('installer.ps1','stop_studio_elevated.ps1')){
    $tokens=$null;$errors=$null
    [void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $file),[ref]$tokens,[ref]$errors)
    if($errors.Count){throw ($errors | Out-String)}
  }
  $tokens=$null;$errors=$null
  $ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'installer.ps1'),[ref]$tokens,[ref]$errors)
  $fn=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Test-AccessDenied'},$true)
  . ([scriptblock]::Create($fn.Extent.Text))
  foreach($kind in @('direct','nested','missing')){
    $ex=if($kind -eq 'direct'){[System.UnauthorizedAccessException]::new('Denied')}elseif($kind -eq 'nested'){[System.InvalidOperationException]::new('Wrapped',[System.ComponentModel.Win32Exception]::new(5))}else{[System.ComponentModel.Win32Exception]::new(2)}
    $record=[System.Management.Automation.ErrorRecord]::new($ex,'test',[System.Management.Automation.ErrorCategory]::CloseError,$null)
    if((Test-AccessDenied $record) -ne ($kind -ne 'missing')){throw ('Wrong access-denied classification: '+$kind)}
    Write-Output ('PASS denial '+$kind)
  }
  foreach($case in @('success','wrong_app','wrong_pid','wrong_root','unknown_jobs','busy','wrong_process','wrong_listener','network','denied')){
    $global:BazorStopTestState.scenario=$case;$global:BazorStopTestState.stops=@();$global:LASTEXITCODE=99
    & (Join-Path $PSScriptRoot 'stop_studio_elevated.ps1') -StudioRoot $root -ExpectedPid 111
    $expected=if($case -eq 'success'){0}else{1}
    if($LASTEXITCODE -ne $expected){throw ('Unexpected exit for '+$case+': '+$LASTEXITCODE)}
    if($case -eq 'success'){
      if($global:BazorStopTestState.stops.Count -ne 1 -or $global:BazorStopTestState.stops[0] -ne 111){throw 'Wrong stop target'}
    }elseif($global:BazorStopTestState.stops.Count){throw ('Unsafe stop for '+$case)}
    Write-Output ('PASS '+$case)
  }
  Write-Output 'PASS 13 Windows scenarios; UAC and real GPU remain untested.'
  $global:LASTEXITCODE=0
} finally {Remove-Item -LiteralPath $root -Recurse -Force; Remove-Variable -Name BazorStopTestState -Scope Global}
