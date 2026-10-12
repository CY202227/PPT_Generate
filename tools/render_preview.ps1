param([Parameter(Mandatory = $true)][string]$PptxPath)
$ErrorActionPreference = 'Stop'
$resolvedPptx = (Resolve-Path -LiteralPath $PptxPath).Path
$previewDirectory = Join-Path (Split-Path -Parent $resolvedPptx) 'previews'
$resourceScript = Join-Path $PSScriptRoot '../ppt_generate/resources/powerpoint_preview.ps1'
& $resourceScript -PptxPath $resolvedPptx -OutputDirectory $previewDirectory
Write-Output $previewDirectory
