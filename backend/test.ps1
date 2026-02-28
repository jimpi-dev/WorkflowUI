# Run backend tests (pytest).
# From backend folder:  .\test.ps1   (PowerShell requires .\ prefix)
# From repo root:       .\backend\test.ps1
# With coverage:        .\test.ps1 -Coverage
param([switch]$Coverage)

$ErrorActionPreference = "Stop"
$BackendDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
Set-Location $BackendDir

if ($Coverage) {
    python -m pytest tests\ -v --tb=short --cov=services --cov=repositories --cov-report=term-missing
} else {
    python -m pytest tests\ -v --tb=short
}
exit $LASTEXITCODE
