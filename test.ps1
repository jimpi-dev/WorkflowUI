# WorkflowUI — Run frontend tests
# Usage: .\test.ps1 [run|coverage]
#   no args = watch mode; run = single run; coverage = single run with coverage

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot
if (-not $RootDir) { $RootDir = Get-Location }
$FrontendDir = Join-Path $RootDir "frontend"

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    Write-Error "Frontend not found at $FrontendDir"
    exit 1
}

$mode = $args[0]
$script = switch ($mode) {
    "run"     { "test:run" }
    "coverage" { "test:coverage" }
    default   { "test" }
}

Push-Location $FrontendDir
try {
    npm run $script
} finally {
    Pop-Location
}
