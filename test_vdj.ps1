$ErrorActionPreference = 'SilentlyContinue'
$logDir = "$env:LOCALAPPDATA\VDJ-GPU-Proxy"
Write-Host "Log Dir: $logDir"

if (Test-Path $logDir) {
    Remove-Item "$logDir\*" -Force
}

Write-Host "Launching VirtualDJ..."
$proc = Start-Process "C:\Program Files\VirtualDJ\VirtualDJ.exe" -PassThru
Start-Sleep -Seconds 15

if (-not $proc.HasExited) {
    Write-Host "Stopping VirtualDJ..."
    Stop-Process -Id $proc.Id -Force
}

Write-Host "Done."
