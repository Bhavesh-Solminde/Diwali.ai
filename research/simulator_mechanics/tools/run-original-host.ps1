param([ValidateSet('04','05')][string]$Version,[string]$WorkspaceRoot,[string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$researchRoot = Split-Path $PSScriptRoot
$workspace = if ($WorkspaceRoot) { (Resolve-Path $WorkspaceRoot).Path } else { Split-Path $researchRoot }
$output = if ($OutputDirectory) { [IO.Path]::GetFullPath($OutputDirectory) } else { Join-Path $researchRoot 'evidence/original-host' }
if (Test-Path (Join-Path $output "runs-v$Version.csv")) { throw 'Completed output exists. Choose a fresh -OutputDirectory.' }
$relative = if ($Version -eq '04') { 'Krafer Agent Trader Sim/Kat0-4(Win)/Kat 0.4/MarketSimulation_Data/Managed' } else { 'Krafer Agent Trader Sim/Kat-05(Win)/Market Simulation/MarketSimulation_Data/Managed' }
$managed = (Resolve-Path (Join-Path $workspace $relative)).Path
Add-Type -Path (Join-Path $PSScriptRoot 'OriginalHost.cs')
[OriginalHost]::Run($managed,$Version,$output)
