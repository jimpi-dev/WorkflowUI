# WorkflowUI — One-time setup: install backend and frontend dependencies
# Run from WorkflowUI root: .\install.ps1

$ErrorActionPreference = "Stop"
$RootDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
$VenvDir = Join-Path $RootDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Get-SystemPython {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

Write-Host "WorkflowUI: installing dependencies..."
Write-Host ""

Write-Host "Backend (Python): virtualenv at .venv + pip install -r backend\requirements.txt"
$systemPython = Get-SystemPython
if (-not $systemPython) {
    Write-Error "Python 3.x was not found. Install Python and ensure it is on PATH."
    exit 1
}
if (-not (Test-Path $VenvPython)) {
    Write-Host "  Creating virtual environment at $VenvDir ..."
    if ((Split-Path $systemPython -Leaf) -eq "py.exe") {
        & $systemPython -3 -m venv $VenvDir
    } else {
        & $systemPython -m venv $VenvDir
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        Write-Error "Failed to create virtualenv at $VenvDir"
        exit 1
    }
}
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend pip upgrade failed."
    exit 1
}
& $VenvPython -m pip install -r (Join-Path $RootDir "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend install failed. Ensure Python 3.x is installed."
    exit 1
}

Write-Host ""
Write-Host "Frontend (Node): npm install in frontend/"
Set-Location (Join-Path $RootDir "frontend")
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend install failed. Ensure Node.js and npm are installed."
    exit 1
}
Set-Location $RootDir

Write-Host ""
Write-Host "ffmpeg (video thumbnails + GenVault HEVC compress — optional but recommended)..."
function Test-FfmpegHevc {
    param([string]$FfmpegExe)
    try {
        $out = & $FfmpegExe -hide_banner -encoders 2>&1 | Out-String
        return $out -match "libx265"
    } catch {
        return $false
    }
}
function Ensure-Ffmpeg {
    $existing = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Already installed: $($existing.Source)"
        return $true
    }
    Write-Host "  Not found; attempting install..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  winget reported success. If 'ffmpeg' is still not found, open a new terminal (PATH refresh)."
            return $true
        }
    }
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install ffmpeg -y
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Chocolatey reported success. If 'ffmpeg' is still not found, open a new terminal."
            return $true
        }
    }
    if (Get-Command scoop -ErrorAction SilentlyContinue) {
        scoop install ffmpeg
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    Write-Host "  Could not install automatically. Install ffmpeg manually, e.g.:"
    Write-Host "    winget install -e --id Gyan.FFmpeg"
    Write-Host "  Or download: https://ffmpeg.org/download.html#build-windows"
    return $false
}
$null = Ensure-Ffmpeg
$ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegCmd) {
    Write-Host "  ffmpeg is available: $($ffmpegCmd.Source)"
    if (Test-FfmpegHevc -FfmpegExe $ffmpegCmd.Source) {
        Write-Host "  libx265 (HEVC): available — GenVault video compression enabled."
    } else {
        Write-Host "  libx265 (HEVC): not found in this build. GenVault video compress disabled."
        Write-Host "  Use a full build, e.g.: winget install -e --id Gyan.FFmpeg"
    }
} else {
    Write-Host "  Note: ffmpeg not on PATH yet (or not installed). Video thumbnails may fail unless ComfyUI serves previews."
    Write-Host "  GenVault video compression (HEVC) also requires ffmpeg with libx265."
    Write-Host "  After winget/choco/scoop install, open a new terminal or log off/on so PATH updates."
}

Write-Host ""
Write-Host "Done. Start the app with: .\start.ps1   (dev: .\start-dev.ps1)"
Write-Host "Optional: copy .env.example to .env and set COMFYUI_URL if needed."
