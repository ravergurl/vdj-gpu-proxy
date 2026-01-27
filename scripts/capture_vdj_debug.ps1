# Capture VirtualDJ debug output using DebugView

$ErrorActionPreference = 'Continue'

$dbgview = "C:\Users\peopl\work\vdj\DebugView\Dbgview64.exe"
$outputLog = "C:\Users\peopl\work\vdj\vdj_debug.log"
$vdjPath = "C:\Program Files\VirtualDJ\virtualdj.exe"

# Kill any existing instances
Write-Host "Stopping existing processes..."
Stop-Process -Name "Dbgview64" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "virtualdj" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Remove old log
if (Test-Path $outputLog) {
    Remove-Item $outputLog -Force
}

Write-Host "Starting DebugView in capture mode..."
# Start DebugView with auto-scroll and Win32 capture enabled
# /accepteula - accept EULA automatically
# /l - log to file
# /g - capture global win32 messages
# /t - timestamp
Start-Process -FilePath $dbgview -ArgumentList "/accepteula","/l",$outputLog,"/g","/t" -PassThru | Out-Null
Start-Sleep -Seconds 3

Write-Host "Starting VirtualDJ..."
Write-Host "Please load a track and enable stems separation"
Write-Host "Press Ctrl+C when done capturing"
Write-Host ""

Start-Process -FilePath $vdjPath

# Wait for user input
Read-Host "Press Enter when you've triggered stems separation..."

Write-Host "Stopping capture..."
Stop-Process -Name "Dbgview64" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "virtualdj" -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

if (Test-Path $outputLog) {
    Write-Host ""
    Write-Host "Debug log saved to: $outputLog"
    Write-Host ""
    Write-Host "Filtering for VDJ-GPU-Proxy messages:"
    Write-Host "======================================"
    Get-Content $outputLog | Select-String -Pattern "VDJ-GPU-Proxy|HTTP:" | ForEach-Object { $_.Line }
} else {
    Write-Host "No log file created - DebugView may need administrator privileges"
}
