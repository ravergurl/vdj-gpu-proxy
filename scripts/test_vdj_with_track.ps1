# VDJ test with automatic track loading and stems triggering
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms

$dbgview = "C:\Users\peopl\work\vdj\DebugView\Dbgview64.exe"
$outputLog = "C:\Users\peopl\work\vdj\vdj_debug.log"
$vdjPath = "C:\Program Files\VirtualDJ\virtualdj.exe"

Write-Host "=== VDJ Automated Stems Test ===`n" -ForegroundColor Cyan

# Cleanup
Write-Host "Cleaning up..." -ForegroundColor Yellow
Get-Process | Where-Object { $_.ProcessName -like "*Dbgview*" -or $_.ProcessName -eq "virtualdj" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

if (Test-Path $outputLog) {
    Remove-Item $outputLog -Force
}

# Find a music file to test with
Write-Host "Looking for test audio file..." -ForegroundColor Cyan
$testFile = Get-ChildItem -Path "$env:USERPROFILE\Music" -Filter "*.mp3" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $testFile) {
    Write-Host "ERROR: No MP3 files found in Music folder" -ForegroundColor Red
    Write-Host "Please place an MP3 file in $env:USERPROFILE\Music"
    exit 1
}

Write-Host "  Found: $($testFile.FullName)`n"

# Start DebugView
Write-Host "Starting DebugView..." -ForegroundColor Green
$dbgProc = Start-Process -FilePath $dbgview -ArgumentList "/accepteula","/l",$outputLog,"/g","/t" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3

# Start VirtualDJ with the test file
Write-Host "Starting VirtualDJ with test file..." -ForegroundColor Green
$vdjProc = Start-Process -FilePath $vdjPath -ArgumentList """$($testFile.FullName)""" -PassThru
Write-Host "  Process ID: $($vdjProc.Id)`n"

# Wait for VDJ to fully load
Write-Host "Waiting 10 seconds for VirtualDJ to load..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Try to activate VDJ window and trigger stems
Write-Host "Attempting to trigger stems separation..." -ForegroundColor Cyan

# Find VDJ window
$vdjWindow = Get-Process -Id $vdjProc.Id -ErrorAction SilentlyContinue
if ($vdjWindow) {
    # Load Windows Forms for SendKeys
    [void][System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")

    # Give VDJ focus
    Start-Sleep -Milliseconds 500

    # Try keyboard shortcut for stems (if it exists)
    # VDJ doesn't have a standard shortcut, so we just wait for it to auto-process
    Write-Host "  Waiting 60 seconds for stems processing to complete..." -ForegroundColor Yellow
    Start-Sleep -Seconds 60
} else {
    Write-Host "  WARNING: Could not find VDJ window" -ForegroundColor Yellow
    Start-Sleep -Seconds 30
}

# Stop processes
Write-Host "`nStopping processes..." -ForegroundColor Yellow
Stop-Process -Id $vdjProc.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $dbgProc.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Read and display debug output
Write-Host "`n=== Debug Output ===" -ForegroundColor Cyan

if (Test-Path $outputLog) {
    $content = Get-Content $outputLog
    Write-Host "Total lines captured: $($content.Count)`n"

    $proxyLines = $content | Select-String -Pattern "VDJ-GPU-Proxy|HTTP:"

    if ($proxyLines) {
        Write-Host "VDJ-GPU-Proxy messages:" -ForegroundColor Green
        Write-Host "==============================" -ForegroundColor Green
        $proxyLines | ForEach-Object { Write-Host $_.Line }

        # Check for specific error indicators
        $errors = $proxyLines | Select-String -Pattern "FAIL|ERROR|CRASH"
        if ($errors) {
            Write-Host "`nERROR MESSAGES FOUND:" -ForegroundColor Red
            $errors | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
        }
    } else {
        Write-Host "No VDJ-GPU-Proxy messages found" -ForegroundColor Red
        Write-Host "`nFirst 50 lines:" -ForegroundColor Yellow
        $content | Select-Object -First 50 | ForEach-Object { Write-Host $_ }
    }
} else {
    Write-Host "No debug log created" -ForegroundColor Red
}

Write-Host "`nLog file: $outputLog" -ForegroundColor Cyan
