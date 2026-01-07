# Install VDJ GPU Proxy DLL

param(
    [string]$VdjPath = "",
    [string]$ServerAddress = "127.0.0.1",
    [int]$ServerPort = 50051
)

$ErrorActionPreference = "Stop"

# Find VirtualDJ installation
if (-not $VdjPath) {
    $possiblePaths = @(
        "$env:ProgramFiles\VirtualDJ",
        "${env:ProgramFiles(x86)}\VirtualDJ",
        "$env:LOCALAPPDATA\VirtualDJ"
    )

    foreach ($path in $possiblePaths) {
        if (Test-Path (Join-Path $path "VirtualDJ.exe")) {
            $VdjPath = $path
            break
        }
    }
}

if (-not $VdjPath -or -not (Test-Path $VdjPath)) {
    Write-Error "VirtualDJ installation not found. Please specify -VdjPath"
    exit 1
}

Write-Host "VirtualDJ found at: $VdjPath"

$ortDll = Join-Path $VdjPath "onnxruntime.dll"
$ortRealDll = Join-Path $VdjPath "onnxruntime_real.dll"
$proxyDll = Join-Path $PSScriptRoot "..\build\Release\onnxruntime.dll"

# Backup original
if (Test-Path $ortDll) {
    if (-not (Test-Path $ortRealDll)) {
        Write-Host "Backing up original onnxruntime.dll..."
        Copy-Item $ortDll $ortRealDll
    }
}

# Copy proxy DLL
if (-not (Test-Path $proxyDll)) {
    Write-Error "Proxy DLL not found. Build the project first."
    exit 1
}

Write-Host "Installing proxy DLL..."
Copy-Item $proxyDll $ortDll -Force

# Configure registry
Write-Host "Configuring settings..."
$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}

Set-ItemProperty -Path $regPath -Name "ServerAddress" -Value $ServerAddress
Set-ItemProperty -Path $regPath -Name "ServerPort" -Value $ServerPort
Set-ItemProperty -Path $regPath -Name "Enabled" -Value 1

Write-Host ""
Write-Host "Installation complete!"
Write-Host "Server: ${ServerAddress}:${ServerPort}"
