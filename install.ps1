# WorkflowUI — One-time setup: install backend and frontend dependencies
# Run from WorkflowUI root: .\install.ps1

$ErrorActionPreference = "Stop"
$RootDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }

Write-Host "WorkflowUI: installing dependencies..."
Write-Host ""

Write-Host "Backend (Python): pip install -r backend\requirements.txt"
Set-Location $RootDir\backend
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend install failed. Ensure Python 3.x and pip are installed."
    exit 1
}
Set-Location $RootDir

Write-Host ""
Write-Host "Frontend (Node): npm install in frontend/"
Set-Location $RootDir\frontend
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend install failed. Ensure Node.js and npm are installed."
    exit 1
}
Set-Location $RootDir

Write-Host ""
Write-Host "ffmpeg (video output thumbnails — optional but recommended)..."
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
} else {
    Write-Host "  Note: ffmpeg not on PATH yet (or not installed). Video WebP thumbnails may fail unless ComfyUI serves previews."
    Write-Host "  After winget/choco/scoop install, open a new terminal or log off/on so PATH updates."
}

Write-Host ""
Write-Host "Done. Start the app with: .\start.ps1"
Write-Host "Optional: copy .env.example to .env and set COMFYUI_URL if needed."
