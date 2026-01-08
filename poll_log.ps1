$ErrorActionPreference = 'SilentlyContinue'
$logPath = "C:\Users\peopl\AppData\Local\VDJ-GPU-Proxy"
Write-Host "Polling for logs in $logPath..."

if (Test-Path $logPath) {
    Remove-Item "$logPath\*" -Force
} else {
    New-Item -ItemType Directory -Path $logPath -Force | Out-Null
}

$proc = Start-Process "C:\Program Files\VirtualDJ\VirtualDJ.exe" -PassThru
$found = $false

for ($i = 0; $i -lt 60; $i++) {
    $files = Get-ChildItem "$logPath\*.log"
    if ($files) {
        Write-Host "LOG FOUND: $($files[0].Name)"
        $found = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $found) {
    Write-Host "LOG NOT FOUND after 60 seconds."
}

Stop-Process -Id $proc.Id -Force
