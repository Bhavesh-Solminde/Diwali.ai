param([ValidateSet('pilot','main')][string]$Phase, [Parameter(Mandatory)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path (Split-Path $PSScriptRoot))
$managed = Join-Path $root 'Krafer Agent Trader Sim/Kat0-4(Win)/Kat 0.4/MarketSimulation_Data/Managed'
Add-Type -Path @((Join-Path $PSScriptRoot 'OriginalHost.cs'),(Join-Path $PSScriptRoot 'FlowHost.cs'))
[FlowHost]::Run($managed,[IO.Path]::GetFullPath($OutputDirectory),$Phase)
