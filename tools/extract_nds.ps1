<#
.SYNOPSIS
  Extrae el sistema de archivos de una ROM NDS a work/<Name>/.
.DESCRIPTION
  Envoltorio de una orden: `ie123 extraer nds` (ie123kit, Python puro: ya no hace falta
  ndstool). Salida como la de nds_unpack: work/<Name>/data_iz/... Usalo con las ROMs de
  referencia en espanol.
.EXAMPLE
  pwsh ./tools/extract_nds.ps1 -Rom "Roms\ie1\Inazuma Eleven (2011).nds" -Name ie1\fuentes\nds_es
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string]$Rom,
  [Parameter(Mandatory)] [string]$Name
)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = Join-Path $repo "tools\src"
& python -X utf8 -m ie123kit.cli --proyecto $repo extraer nds --rom (Join-Path $repo $Rom) `
  --salida (Join-Path $repo (Join-Path "work" $Name))
exit $LASTEXITCODE
