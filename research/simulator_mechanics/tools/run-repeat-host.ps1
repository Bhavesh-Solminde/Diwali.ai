param([ValidateSet('pilot','main')][string]$Phase,[Parameter(Mandatory)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path (Split-Path $PSScriptRoot))
$managed = Join-Path $root 'Krafer Agent Trader Sim/Kat-05(Win)/Market Simulation/MarketSimulation_Data/Managed'
Add-Type -Path @((Join-Path $PSScriptRoot 'OriginalHost.cs'),(Join-Path $PSScriptRoot 'RepeatHost.cs'))
[RepeatHost]::Run($managed,[IO.Path]::GetFullPath($OutputDirectory),$Phase)
