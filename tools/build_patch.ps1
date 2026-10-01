<#
.SYNOPSIS
  Genera el parche xdelta a partir de la ROM original y la ROM traducida.
.DESCRIPTION
  Envoltorio de una orden: `ie123 parche` (ie123kit). Localiza xdelta3 en tools/bin, en
  [herramientas] de ie123.local.toml o en el PATH. El parche es el UNICO entregable que se
  distribuye (no contiene datos originales del juego).
.EXAMPLE
  pwsh ./tools/build_patch.ps1 -Translated "build\123_es.3ds"
#>
[CmdletBinding()]
param(
  [string]$Original   = "Roms\shared\Inazuma Eleven 1-2-3!! - Endou Mamoru Densetsu (2012) (Japan).3ds",
  [Parameter(Mandatory)] [string]$Translated,
  [string]$Patch = "patch\inazuma123-es.xdelta"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = Join-Path $repo "tools\src"
& python -X utf8 -m ie123kit.cli --proyecto $repo parche --rom-base (Join-Path $repo $Original) `
  --rom-parcheada (Join-Path $repo $Translated) --salida (Join-Path $repo $Patch)
exit $LASTEXITCODE
