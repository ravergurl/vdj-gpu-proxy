# Generate C++ protobuf/gRPC code from stems.proto

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$ProtoDir = "$RepoRoot\proto"
$OutputDir = "$RepoRoot\proxy-dll\generated"
$ProtoFile = "$ProtoDir\stems.proto"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# Find vcpkg tools
$VcpkgRoot = $env:VCPKG_ROOT
if (-not $VcpkgRoot) {
    if (Test-Path "C:\vcpkg") {
        $VcpkgRoot = "C:\vcpkg"
    } elseif (Test-Path "$env:USERPROFILE\vcpkg") {
        $VcpkgRoot = "$env:USERPROFILE\vcpkg"
    }
}

if (-not $VcpkgRoot) {
    Write-Error "VCPKG_ROOT environment variable not set and vcpkg not found in common locations."
    exit 1
}

Write-Host "Using vcpkg root: $VcpkgRoot"

# Search for protoc and grpc_cpp_plugin in vcpkg installed tools
# We try common paths first for speed, then recurse if not found
$ProtocPaths = @(
    "$VcpkgRoot\installed\x64-windows\tools\protobuf\protoc.exe",
    "$VcpkgRoot\installed\x64-windows-static\tools\protobuf\protoc.exe"
)

$Protoc = $null
foreach ($Path in $ProtocPaths) {
    if (Test-Path $Path) {
        $Protoc = $Path
        break
    }
}

if (-not $Protoc) {
    $ProtocFile = Get-ChildItem -Path "$VcpkgRoot\installed" -Filter "protoc.exe" -Recurse | Select-Object -First 1
    if ($ProtocFile) { $Protoc = $ProtocFile.FullName }
}

$GrpcPluginPaths = @(
    "$VcpkgRoot\installed\x64-windows\tools\grpc\grpc_cpp_plugin.exe",
    "$VcpkgRoot\installed\x64-windows-static\tools\grpc\grpc_cpp_plugin.exe"
)

$GrpcPlugin = $null
foreach ($Path in $GrpcPluginPaths) {
    if (Test-Path $Path) {
        $GrpcPlugin = $Path
        break
    }
}

if (-not $GrpcPlugin) {
    $GrpcPluginFile = Get-ChildItem -Path "$VcpkgRoot\installed" -Filter "grpc_cpp_plugin.exe" -Recurse | Select-Object -First 1
    if ($GrpcPluginFile) { $GrpcPlugin = $GrpcPluginFile.FullName }
}

if (-not $Protoc) {
    Write-Error "Could not find protoc.exe in $VcpkgRoot\installed. Ensure protobuf is installed via vcpkg."
    exit 1
}

if (-not $GrpcPlugin) {
    Write-Error "Could not find grpc_cpp_plugin.exe in $VcpkgRoot\installed. Ensure gRPC is installed via vcpkg."
    exit 1
}

Write-Host "Found protoc: $Protoc"
Write-Host "Found grpc_cpp_plugin: $GrpcPlugin"

# Run generation
Write-Host "Generating C++ proto files..."
& $Protoc --cpp_out=$OutputDir --grpc_out=$OutputDir --plugin=protoc-gen-grpc=$GrpcPlugin "-I$ProtoDir" "$ProtoFile"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Proto generation failed with exit code $LASTEXITCODE"
    exit 1
}

Write-Host "Proto generation complete! Files generated in $OutputDir"
