#Requires -Version 5.1
param(
    [string]$VcpkgRoot = "C:\vcpkg",
    [switch]$SkipVcpkg,
    [switch]$SkipBuild,
    [switch]$SkipPython,
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
Write-Host "  (Ninja + uv for maximum speed)" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

# Check prerequisites
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "Git is required. Install from https://git-scm.com/"
    exit 1
}

# Check for Visual Studio (needed for MSVC compiler)
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

# Setup VS Developer Environment for cl.exe
$vcvarsall = Join-Path $vsPath "VC\Auxiliary\Build\vcvars64.bat"
if (Test-Path $vcvarsall) {
    Write-Status "Loading Visual Studio environment..."
    cmd /c "`"$vcvarsall`" x64 >nul 2>&1 && set" | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

# Install/check CMake
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Status "Installing CMake via winget..."
    winget install Kitware.CMake --silent --accept-package-agreements --accept-source-agreements
    $env:Path = "$env:ProgramFiles\CMake\bin;$env:Path"
}
Write-Success "CMake: $(cmake --version | Select-Object -First 1)"

# Install/check Ninja (FAST build system)
if (-not (Get-Command ninja -ErrorAction SilentlyContinue)) {
    Write-Status "Installing Ninja via winget..."
    winget install Ninja-build.Ninja --silent --accept-package-agreements --accept-source-agreements
    # Add common ninja locations to path
    $ninjaPath = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Ninja-build.Ninja_Microsoft.Winget.Source_8wekyb3d8bbwe"
    if (Test-Path $ninjaPath) {
        $env:Path = "$ninjaPath;$env:Path"
    }
}
if (Get-Command ninja -ErrorAction SilentlyContinue) {
    Write-Success "Ninja: $(ninja --version)"
} else {
    Write-Warn "Ninja not found - will fall back to MSBuild (slower)"
}

# Install/check uv (FAST Python package manager)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Status "Installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Success "uv: $(uv --version)"
}

# ============================================
# VCPKG SETUP
# ============================================
if (-not $SkipVcpkg) {
    Write-Status "Setting up vcpkg..."
    
    if (-not (Test-Path "$VcpkgRoot\vcpkg.exe")) {
        Write-Status "Cloning vcpkg to $VcpkgRoot..."
        git clone --depth 1 https://github.com/microsoft/vcpkg.git $VcpkgRoot
        
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
    
    # Use manifest mode for faster/cached installs
    Write-Status "Installing C++ dependencies via vcpkg (first run takes 15-30 min)..."
    
    # Install all at once (faster than one-by-one)
    & "$VcpkgRoot\vcpkg.exe" install grpc:x64-windows protobuf:x64-windows gtest:x64-windows --triplet x64-windows
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to install vcpkg packages"
        exit 1
    }
    
    Write-Success "All C++ dependencies installed"
}

# ============================================
# C++ BUILD (Ninja = ~3-5x faster than MSBuild)
# ============================================
if (-not $SkipBuild) {
    $buildDir = Join-Path $RepoRoot "build"
    
    if ($Clean -and (Test-Path $buildDir)) {
        Write-Status "Cleaning build directory..."
        Remove-Item -Recurse -Force $buildDir
    }
    
    if (-not (Test-Path $buildDir)) {
        New-Item -ItemType Directory -Path $buildDir | Out-Null
    }
    
    Write-Status "Configuring CMake with Ninja..."
    Push-Location $buildDir
    
    $toolchainFile = "$VcpkgRoot\scripts\buildsystems\vcpkg.cmake"
    
    # Prefer Ninja, fallback to MSBuild
    $generator = if (Get-Command ninja -ErrorAction SilentlyContinue) { "Ninja" } else { "Visual Studio 17 2022" }
    
    if ($generator -eq "Ninja") {
        cmake -G Ninja `
            -DCMAKE_BUILD_TYPE=Release `
            -DCMAKE_TOOLCHAIN_FILE="$toolchainFile" `
            -DCMAKE_C_COMPILER=cl `
            -DCMAKE_CXX_COMPILER=cl `
            -DBUILD_TESTS=ON `
            -DENABLE_UNITY_BUILD=ON `
            ..
    } else {
        cmake -G "Visual Studio 17 2022" -A x64 `
            -DCMAKE_TOOLCHAIN_FILE="$toolchainFile" `
            -DCMAKE_BUILD_TYPE=Release `
            -DBUILD_TESTS=ON `
            -DENABLE_UNITY_BUILD=ON `
            ..
    }
    
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Err "CMake configuration failed"
        exit 1
    }
    
    Write-Status "Building project (parallel)..."
    $numCores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    cmake --build . --config Release --parallel $numCores
    
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Err "Build failed"
        exit 1
    }
    
    Pop-Location
    Write-Success "C++ build completed"
    
    # Check for output
    $dllPath = Join-Path $buildDir "proxy-dll\onnxruntime.dll"
    if (-not (Test-Path $dllPath)) {
        $dllPath = Join-Path $buildDir "proxy-dll\Release\onnxruntime.dll"
    }
    if (Test-Path $dllPath) {
        Write-Success "Proxy DLL: $dllPath"
    }
    
    # Run C++ tests
    Write-Status "Running C++ tests..."
    Push-Location $buildDir
    ctest -C Release --output-on-failure --parallel $numCores
    $testResult = $LASTEXITCODE
    Pop-Location
    
    if ($testResult -eq 0) {
        Write-Success "All C++ tests passed"
    } else {
        Write-Warn "Some C++ tests failed (exit code: $testResult)"
    }
}

# ============================================
# PYTHON SETUP (uv = ~10-100x faster than pip)
# ============================================
if (-not $SkipPython) {
    Write-Status "Setting up Python server with uv..."
    
    $serverDir = Join-Path $RepoRoot "server"
    Push-Location $serverDir
    
    # Create venv with uv
    if (-not (Test-Path ".venv")) {
        uv venv
    }
    
    # Install deps with uv (blazing fast)
    Write-Status "Installing Python dependencies..."
    uv pip install -e ".[dev]"
    
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Err "Python dependency installation failed"
        exit 1
    }
    
    Pop-Location
    
    # Generate proto files
    Write-Status "Generating Python proto files..."
    Push-Location $RepoRoot
    & "$serverDir\.venv\Scripts\python.exe" scripts/generate_proto.py
    Pop-Location
    
    Write-Success "Python setup completed"
    
    # Run Python tests
    Write-Status "Running Python tests..."
    Push-Location $serverDir
    & ".venv\Scripts\python.exe" -m pytest tests/ -v --tb=short
    $pytestResult = $LASTEXITCODE
    Pop-Location
    
    if ($pytestResult -eq 0) {
        Write-Success "All Python tests passed"
    } else {
        Write-Warn "Some Python tests failed (exit code: $pytestResult)"
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Install proxy: .\scripts\install_proxy.ps1 -ServerAddress <GPU_SERVER_IP>"
Write-Host "  2. Start server:  cd server && .venv\Scripts\activate && vdj-stems-server --host 0.0.0.0"
Write-Host ""
