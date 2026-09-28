$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Ffmpeg = Join-Path $ProjectRoot "vendor\ffmpeg\bin\ffmpeg.exe"
$Ffprobe = Join-Path $ProjectRoot "vendor\ffmpeg\bin\ffprobe.exe"
$IconDir = Join-Path $ProjectRoot "build\icon"
$IconIco = Join-Path $IconDir "app_icon.ico"

if (-not (Test-Path $Ffmpeg) -or -not (Test-Path $Ffprobe)) {
    Write-Host ""
    Write-Host "FFmpeg binaries were not found in vendor\ffmpeg\bin." -ForegroundColor Yellow
    Write-Host "Place ffmpeg.exe and ffprobe.exe there before building a self-contained EXE."
    Write-Host ""
    exit 1
}

Write-Host "Preparing application icon..."
python -m ratanak_media_converter.icon_data --output-dir $IconDir

if (-not (Test-Path $IconIco)) {
    throw "Application icon generation failed: $IconIco was not created."
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "RatanakMediaConverter" `
    --icon "$IconIco" `
    --add-binary "$Ffmpeg;ffmpeg\bin" `
    --add-binary "$Ffprobe;ffmpeg\bin" `
    main.py

Write-Host ""
Write-Host "Build complete: dist\RatanakMediaConverter\RatanakMediaConverter.exe" -ForegroundColor Green
