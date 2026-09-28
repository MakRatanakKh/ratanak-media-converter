$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Ffmpeg = Join-Path $ProjectRoot "vendor\ffmpeg\bin\ffmpeg.exe"
$Ffprobe = Join-Path $ProjectRoot "vendor\ffmpeg\bin\ffprobe.exe"

if (-not (Test-Path $Ffmpeg) -or -not (Test-Path $Ffprobe)) {
    Write-Host ""
    Write-Host "FFmpeg binaries were not found in vendor\ffmpeg\bin." -ForegroundColor Yellow
    Write-Host "Place ffmpeg.exe and ffprobe.exe there before building a self-contained EXE."
    Write-Host ""
    exit 1
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "RatanakMediaConverter" `
    --add-binary "$Ffmpeg;ffmpeg\bin" `
    --add-binary "$Ffprobe;ffmpeg\bin" `
    main.py

Write-Host ""
Write-Host "Build complete: dist\RatanakMediaConverter\RatanakMediaConverter.exe" -ForegroundColor Green
