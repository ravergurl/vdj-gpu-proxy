$ErrorActionPreference = 'Stop'
$vdj = 'C:\Program Files\VirtualDJ'
$dll = Join-Path $vdj 'onnxruntime.dll'
$real = Join-Path $vdj 'onnxruntime_real.dll'
$new = 'artifacts\onnxruntime.dll'

Write-Host "Target: $vdj"

if (-not (Test-Path $real)) {
    Write-Host "Backing up original..."
    Copy-Item $dll $real
}

Write-Host "Installing new DLL..."
Copy-Item $new $dll -Force

Write-Host "Configuring Registry..."
$reg = 'HKCU:\Software\VDJ-GPU-Proxy'
if (-not (Test-Path $reg)) { New-Item $reg -Force | Out-Null }
Set-ItemProperty $reg 'Enabled' 1
Set-ItemProperty $reg 'ServerAddress' '127.0.0.1'
Set-ItemProperty $reg 'ServerPort' 50051

Write-Host "Installation Success!"
