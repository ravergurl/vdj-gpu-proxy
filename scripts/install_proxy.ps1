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

if (-not $VdjPath -or -not (Test-Path (Join-Path $VdjPath "VirtualDJ.exe"))) {
    Write-Error "VirtualDJ not found. Specify -VdjPath"
    exit 1
}

$vdjProcess = Get-Process VirtualDJ -ErrorAction SilentlyContinue
if ($vdjProcess) {
    Write-Error "Close VirtualDJ first"
    exit 1
}

Write-Host "VirtualDJ: $VdjPath"

$scriptRoot = $PSScriptRoot
$projectRoot = Split-Path $scriptRoot -Parent

$proxyDllCandidates = @(
    (Join-Path $projectRoot "artifacts\proxy-dll-windows\onnxruntime.dll"),
    (Join-Path $projectRoot "build\proxy-dll\Release\onnxruntime.dll"),
    (Join-Path $projectRoot "build\proxy-dll\onnxruntime.dll"),
    (Join-Path $scriptRoot "onnxruntime.dll")
)

$proxyDll = ""
foreach ($candidate in $proxyDllCandidates) {
    if (Test-Path $candidate) {
        $proxyDll = (Resolve-Path $candidate).Path
        break
    }
}

if (-not $proxyDll) {
    Write-Error "Proxy DLL not found. Download from GitHub Actions or build first."
    exit 1
}

Write-Host "Proxy DLL: $proxyDll"

$ortDll = Join-Path $VdjPath "onnxruntime.dll"
$ortRealDll = Join-Path $VdjPath "onnxruntime_real.dll"

if ((Test-Path $ortDll) -and -not (Test-Path $ortRealDll)) {
    Write-Host "Backing up original DLL..."
    Copy-Item $ortDll $ortRealDll -ErrorAction Stop
}

Write-Host "Installing proxy..."
Copy-Item $proxyDll $ortDll -Force

$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
Set-ItemProperty -Path $regPath -Name "ServerAddress" -Value $ServerAddress
Set-ItemProperty -Path $regPath -Name "ServerPort" -Value $ServerPort
Set-ItemProperty -Path $regPath -Name "Enabled" -Value 1

Write-Host ""
Write-Host "Installed! Server: ${ServerAddress}:${ServerPort}"
Write-Host "Start VirtualDJ to use GPU stems."
