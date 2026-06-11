param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$addonRoot = Join-Path $ProjectRoot "home-assistant-addon\budget-tracker"
$sourceRoot = Join-Path $addonRoot "app-src"
$resolvedAddonRoot = (Resolve-Path $addonRoot).Path
$resolvedSourceRoot = [System.IO.Path]::GetFullPath($sourceRoot)

if (-not $resolvedSourceRoot.StartsWith($resolvedAddonRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to package outside the add-on folder: $resolvedSourceRoot"
}

if (Test-Path $sourceRoot) {
    Remove-Item -LiteralPath $sourceRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $sourceRoot | Out-Null

$backendSource = Join-Path $ProjectRoot "backend"
$backendTarget = Join-Path $sourceRoot "backend"
$frontendSource = Join-Path $ProjectRoot "frontend"
$frontendTarget = Join-Path $sourceRoot "frontend"

robocopy $backendSource $backendTarget /E /XD "__pycache__" ".pytest_cache" "budget_tracker_backend.egg-info" /XF "*.pyc" | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "Failed to copy backend source. Robocopy exit code: $LASTEXITCODE"
}

robocopy $frontendSource $frontendTarget /E /XD "node_modules" "dist" ".vite" ".vite-temp" /XF "tsconfig.tsbuildinfo" | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "Failed to copy frontend source. Robocopy exit code: $LASTEXITCODE"
}

Write-Host "Home Assistant add-on source packaged at $sourceRoot"
