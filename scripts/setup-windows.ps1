#Requires -Version 5.1
param(
    [string]$VcpkgRoot = "C:\vcpkg",
    [switch]$SkipVcpkg,
    [switch]$SkipBuild,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."

function Write-Status($msg) { Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[+] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[-] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  VDJ-GPU-Proxy Windows Setup" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "Git is required. Install from https://git-scm.com/"
    exit 1
}

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Err "CMake is required. Install from https://cmake.org/"
    exit 1
}

$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vsWhere)) {
    Write-Err "Visual Studio 2019+ required. Install from https://visualstudio.microsoft.com/"
    exit 1
}

$vsPath = & $vsWhere -latest -property installationPath
if (-not $vsPath) {
    Write-Err "Visual Studio installation not found"
    exit 1
}
Write-Success "Found Visual Studio at: $vsPath"

if (-not $SkipVcpkg) {
    Write-Status "Setting up vcpkg..."
    
    if (-not (Test-Path "$VcpkgRoot\vcpkg.exe")) {
        Write-Status "Cloning vcpkg to $VcpkgRoot..."
        git clone https://github.com/microsoft/vcpkg.git $VcpkgRoot
        
        Write-Status "Bootstrapping vcpkg..."
        Push-Location $VcpkgRoot
        .\bootstrap-vcpkg.bat -disableMetrics
        Pop-Location
    }
    
    if (-not (Test-Path "$VcpkgRoot\vcpkg.exe")) {
        Write-Err "vcpkg bootstrap failed"
        exit 1
    }
    Write-Success "vcpkg ready at $VcpkgRoot"
    
    $env:VCPKG_ROOT = $VcpkgRoot
    $env:Path = "$VcpkgRoot;$env:Path"
    
    Write-Status "Installing C++ dependencies (this may take 15-30 minutes on first run)..."
    
    $packages = @(
        "grpc:x64-windows",
        "protobuf:x64-windows", 
        "gtest:x64-windows"
    )
    
    foreach ($pkg in $packages) {
        Write-Status "Installing $pkg..."
        & "$VcpkgRoot\vcpkg.exe" install $pkg --triplet x64-windows
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to install $pkg"
            exit 1
        }
    }
    
    Write-Status "Integrating vcpkg with Visual Studio..."
    & "$VcpkgRoot\vcpkg.exe" integrate install
    
    Write-Success "All C++ dependencies installed"
}

Write-Status "Generating C++ proto files..."
$protoScript = Join-Path $RepoRoot "scripts\generate_proto.ps1"
if (Test-Path $protoScript) {
    & $protoScript
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Proto generation had issues (may be OK if first run)"
    }
}

if (-not $SkipBuild) {
    $buildDir = Join-Path $RepoRoot "build"
    
    if ($Clean -and (Test-Path $buildDir)) {
        Write-Status "Cleaning build directory..."
        Remove-Item -Recurse -Force $buildDir
    }
    
    if (-not (Test-Path $buildDir)) {
        New-Item -ItemType Directory -Path $buildDir | Out-Null
    }
    
    Write-Status "Configuring CMake..."
    Push-Location $buildDir
    
    $toolchainFile = "$VcpkgRoot\scripts\buildsystems\vcpkg.cmake"
    cmake -G "Visual Studio 17 2022" -A x64 `
        -DCMAKE_TOOLCHAIN_FILE="$toolchainFile" `
        -DCMAKE_BUILD_TYPE=Release `
        ..
    
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Err "CMake configuration failed"
        exit 1
    }
    
    Write-Status "Building project..."
    cmake --build . --config Release --parallel
    
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Err "Build failed"
        exit 1
    }
    
    Pop-Location
    Write-Success "Build completed successfully"
    
    $dllPath = Join-Path $buildDir "proxy-dll\Release\onnxruntime.dll"
    if (Test-Path $dllPath) {
        Write-Success "Proxy DLL built: $dllPath"
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Install proxy: .\scripts\install_proxy.ps1 -ServerAddress <GPU_SERVER_IP>"
Write-Host "  2. Setup GPU server: See scripts/setup-server.sh"
Write-Host ""
