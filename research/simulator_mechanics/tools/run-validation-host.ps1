param([ValidateSet('04','05')][string]$Version,[Parameter(Mandatory)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path (Split-Path $PSScriptRoot))
$package=if($Version -eq '04'){'Kat0-4(Win)/Kat 0.4'}else{'Kat-05(Win)/Market Simulation'}
$managed=Join-Path $root "Krafer Agent Trader Sim/$package/MarketSimulation_Data/Managed"
Add-Type -Path @((Join-Path $PSScriptRoot 'OriginalHost.cs'),(Join-Path $PSScriptRoot 'ValidationHost.cs'))
[ValidationHost]::Run($managed,[IO.Path]::GetFullPath($OutputDirectory),$Version)
