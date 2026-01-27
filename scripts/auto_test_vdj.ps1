# Fully automated VDJ debug capture
# This starts DebugView, launches VDJ, waits, then captures output

$ErrorActionPreference = 'Stop'

$dbgview = "C:\Users\peopl\work\vdj\DebugView\Dbgview64.exe"
$outputLog = "C:\Users\peopl\work\vdj\vdj_debug.log"
$vdjPath = "C:\Program Files\VirtualDJ\virtualdj.exe"

Write-Host "=== Automated VDJ Debug Capture ===" -ForegroundColor Cyan
Write-Host ""

# Cleanup
Write-Host "Cleaning up..." -ForegroundColor Yellow
Get-Process | Where-Object { $_.ProcessName -like "*Dbgview*" -or $_.ProcessName -eq "virtualdj" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

if (Test-Path $outputLog) {
    Remove-Item $outputLog -Force
}

# Start DebugView in background capture mode
Write-Host "Starting DebugView..." -ForegroundColor Green
$dbgProc = Start-Process -FilePath $dbgview -ArgumentList "/accepteula","/l",$outputLog,"/g","/t" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3

# Start VirtualDJ
Write-Host "Starting VirtualDJ..." -ForegroundColor Green
$vdjProc = Start-Process -FilePath $vdjPath -PassThru
Write-Host "  Process ID: $($vdjProc.Id)"

# Wait for VirtualDJ to initialize
Write-Host ""
Write-Host "Waiting 15 seconds for VirtualDJ to load..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Check if DLL was loaded
Write-Host ""
Write-Host "Checking loaded modules..." -ForegroundColor Cyan
$modules = Get-Process -Id $vdjProc.Id | Select-Object -ExpandProperty Modules -ErrorAction SilentlyContinue
$ml1151 = $modules | Where-Object { $_.ModuleName -eq "ml1151.dll" }
if ($ml1151) {
    Write-Host "  ml1151.dll is LOADED" -ForegroundColor Green
    Write-Host "  Path: $($ml1151.FileName)"
} else {
    Write-Host "  ml1151.dll NOT LOADED" -ForegroundColor Red
}

# Stop processes
Write-Host ""
Write-Host "Stopping processes..." -ForegroundColor Yellow
Stop-Process -Id $vdjProc.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $dbgProc.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Read and display debug output
Write-Host ""
Write-Host "=== Debug Output ===" -ForegroundColor Cyan

if (Test-Path $outputLog) {
    $content = Get-Content $outputLog
    Write-Host "Total lines captured: $($content.Count)"
    Write-Host ""

    $proxyLines = $content | Select-String -Pattern "VDJ-GPU-Proxy|HTTP:"

    if ($proxyLines) {
        Write-Host "VDJ-GPU-Proxy messages found:" -ForegroundColor Green
        Write-Host "==============================" -ForegroundColor Green
        $proxyLines | ForEach-Object { Write-Host $_.Line }
    } else {
        Write-Host "No VDJ-GPU-Proxy messages found" -ForegroundColor Red
        Write-Host ""
        Write-Host "First 50 lines of output:" -ForegroundColor Yellow
        $content | Select-Object -First 50 | ForEach-Object { Write-Host $_ }
    }
} else {
    Write-Host "No debug log created" -ForegroundColor Red
    Write-Host "DebugView may require administrator privileges" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Log file: $outputLog" -ForegroundColor Cyan
