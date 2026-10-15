$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path -Parent $PSScriptRoot
$destinationRoot = 'C:\Users\MD Tanvir Islam\Desktop\AtlasRec — Personalized Product Recommendation Platform'
$sourceRoot = [System.IO.Path]::GetFullPath($sourceRoot)
$destinationRoot = [System.IO.Path]::GetFullPath($destinationRoot)
if ($sourceRoot -eq $destinationRoot) { Write-Output 'Already in the Desktop project'; exit 0 }
New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
$directories = @('apps','configs','docs','packages','services','scripts','tests','.github')
$rootFiles = @('.dockerignore','.gitignore','.env.example','package.json','package-lock.json','pyproject.toml','uv.lock','PLAN.md','STATUS.md','README.md','compose.yaml','alembic.ini','playwright.config.js')
$files = @()
foreach ($name in $rootFiles) {
    $path = Join-Path $sourceRoot $name
    if (Test-Path -LiteralPath $path -PathType Leaf) { $files += Get-Item -LiteralPath $path }
}
foreach ($name in $directories) {
    $path = Join-Path $sourceRoot $name
    if (Test-Path -LiteralPath $path -PathType Container) {
        $files += Get-ChildItem -LiteralPath $path -Recurse -File -Force | Where-Object { $_.FullName -notmatch '\\(node_modules|\.next|__pycache__|\.pytest_cache|\.ruff_cache)\\' }
    }
}
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourceRoot.Length + 1)
    $target = [System.IO.Path]::GetFullPath((Join-Path $destinationRoot $relative))
    if (-not $target.StartsWith($destinationRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Copy target escaped the Desktop project' }
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
}
Write-Output "Copied $($files.Count) source files to $destinationRoot"
Get-ChildItem -LiteralPath $destinationRoot -Force | Select-Object Name
