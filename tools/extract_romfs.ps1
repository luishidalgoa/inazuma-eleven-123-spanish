<#
.SYNOPSIS
  Extrae ExeFS y RomFS de la ROM 3DS (descifrada) a work/shared/base_3ds.
.DESCRIPTION
  Envoltorio de una orden: `ie123 extraer romfs` (ie123kit). Requiere 3dstool (tools/bin,
  [herramientas] de ie123.local.toml o PATH). La ROM debe estar descifrada (NoCrypto).
  Salida (ignorada por git): work/shared/base_3ds/{exefs,romfs} y las cabeceras.
.EXAMPLE
  pwsh ./tools/extract_romfs.ps1
#>
[CmdletBinding()]
param(
  [string]$Rom = "Roms\shared\Inazuma Eleven 1-2-3!! - Endou Mamoru Densetsu (2012) (Japan).3ds",
  [string]$Out = "work\shared\base_3ds"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = Join-Path $repo "tools\src"
& python -X utf8 -m ie123kit.cli --proyecto $repo extraer romfs --rom (Join-Path $repo $Rom) `
  --salida (Join-Path $repo $Out)
exit $LASTEXITCODE
