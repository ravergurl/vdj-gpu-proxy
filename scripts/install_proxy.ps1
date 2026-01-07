param(
    [string]$VdjPath = "",
    [string]$ServerAddress = "127.0.0.1",
    [int]$ServerPort = 50051
)

$ErrorActionPreference = "Stop"

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

if (-not (Test-Path (Join-Path $VdjPath "VirtualDJ.exe"))) {
    Write-Error "VirtualDJ.exe not found in $VdjPath. Invalid installation path."
    exit 1
}

$vdjProcess = Get-Process VirtualDJ -ErrorAction SilentlyContinue
if ($vdjProcess) {
    Write-Error "VirtualDJ is running. Please close it before installing."
    exit 1
}

Write-Host "VirtualDJ found at: $VdjPath"

$ortDll = Join-Path $VdjPath "onnxruntime.dll"
$ortRealDll = Join-Path $VdjPath "onnxruntime_real.dll"

$proxyDllCandidates = @(
    (Join-Path $PSScriptRoot "..\build\proxy-dll\onnxruntime.dll"),
    (Join-Path $PSScriptRoot "..\build\proxy-dll\Release\onnxruntime.dll"),
    (Join-Path $PSScriptRoot "..\build\proxy-dll\Debug\onnxruntime.dll"),
    (Join-Path $PSScriptRoot "onnxruntime.dll")
)

$proxyDll = ""
foreach ($candidate in $proxyDllCandidates) {
    if (Test-Path $candidate) {
        $proxyDll = $candidate
        break
    }
}

if (-not $proxyDll) {
    Write-Error "Proxy DLL not found. Build the project first."
    exit 1
}

if (Test-Path $ortDll) {
    if (-not (Test-Path $ortRealDll)) {
        Write-Host "Backing up original onnxruntime.dll to onnxruntime_real.dll..."
        Copy-Item $ortDll $ortRealDll -ErrorAction Stop
        if (-not (Test-Path $ortRealDll)) {
            Write-Error "Backup failed. Aborting installation."
            exit 1
        }
    }
}

Write-Host "Installing proxy DLL from $proxyDll..."
Copy-Item $proxyDll $ortDll -Force

$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}

Set-ItemProperty -Path $regPath -Name "ServerAddress" -Value $ServerAddress
Set-ItemProperty -Path $regPath -Name "ServerPort" -Value $ServerPort
Set-ItemProperty -Path $regPath -Name "Enabled" -Value 1

Write-Host "Installation complete!"
Write-Host "Server: ${ServerAddress}:${ServerPort}"
