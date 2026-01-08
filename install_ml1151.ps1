$ErrorActionPreference = 'Stop'

# 1. Cleanup Program Files (Revert previous mistake)
$vdjProg = "C:\Program Files\VirtualDJ"
$progDll = Join-Path $vdjProg "onnxruntime.dll"
$progReal = Join-Path $vdjProg "onnxruntime_real.dll"

if (Test-Path $progReal) {
    Write-Host "Restoring original onnxruntime.dll in Program Files..."
    Copy-Item $progReal $progDll -Force
    Remove-Item $progReal -Force
}

# 2. Target Drivers folder (Actual hook point)
$vdjDrivers = "C:\Users\peopl\AppData\Local\VirtualDJ\Drivers"
$targetDll = Join-Path $vdjDrivers "ml1151.dll"
$targetReal = Join-Path $vdjDrivers "ml1151_real.dll"
$newDll = "C:\Users\peopl\work\vdj\artifacts\onnxruntime.dll"

if (-not (Test-Path $vdjDrivers)) {
    Write-Host "Creating Drivers folder..."
    New-Item -ItemType Directory -Path $vdjDrivers -Force | Out-Null
}

if (-not (Test-Path $targetReal)) {
    if (Test-Path $targetDll) {
        Write-Host "Backing up original ml1151.dll..."
        Copy-Item $targetDll $targetReal -Force
    } else {
        Write-Host "Original ml1151.dll not found. This might be a problem."
    }
}

Write-Host "Installing proxy as ml1151.dll..."
Copy-Item $newDll $targetDll -Force

Write-Host "Installation Complete!"
