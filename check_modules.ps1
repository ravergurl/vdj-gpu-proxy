Start-Process "C:\Program Files\VirtualDJ\VirtualDJ.exe"
Write-Host "Waiting 15 seconds for VDJ to load..."
Start-Sleep -Seconds 15

$proc = Get-Process VirtualDJ -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "VirtualDJ is running (PID: $($proc.Id))"
    $modules = $proc.Modules | Select-Object ModuleName, FileName
    
    Write-Host "`n--- Machine Learning / ONNX Modules ---"
    $modules | Where-Object { $_.ModuleName -match "onnx|ml|direct|media_bin" } | Format-Table -AutoSize
    
    Write-Host "`n--- All Modules ---"
    $modules | Sort-Object ModuleName | Format-Table -AutoSize
    
    Stop-Process -Id $proc.Id -Force
} else {
    Write-Host "VirtualDJ failed to start."
}
