# Uninstall VDJ GPU Proxy DLL

param(
    [string]$VdjPath = ""
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
    Write-Error "VirtualDJ installation not found."
    exit 1
}

$ortDll = Join-Path $VdjPath "onnxruntime.dll"
$ortRealDll = Join-Path $VdjPath "onnxruntime_real.dll"

# Restore original
if (Test-Path $ortRealDll) {
    Write-Host "Restoring original onnxruntime.dll..."
    Copy-Item $ortRealDll $ortDll -Force
    Remove-Item $ortRealDll
} else {
    Write-Warning "Original DLL backup (onnxruntime_real.dll) not found. Cannot restore automatically."
}

# Remove registry settings
$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (Test-Path $regPath) {
    Write-Host "Removing registry settings..."
    Remove-Item -Path $regPath -Recurse
}

Write-Host "Uninstall complete!"
