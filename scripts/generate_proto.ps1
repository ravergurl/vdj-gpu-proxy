# Generate C++ protobuf/gRPC code from stems.proto

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$protoDir = Join-Path $root "proto"
$outputDir = Join-Path $root "proxy-dll" "generated"

# Create output directory
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$protoFile = Join-Path $protoDir "stems.proto"

# Find protoc and grpc_cpp_plugin
$vcpkgRoot = $env:VCPKG_ROOT
if (-not $vcpkgRoot) {
    $vcpkgRoot = "C:\vcpkg"
}

$protoc = Join-Path $vcpkgRoot "installed\x64-windows\tools\protobuf\protoc.exe"
$grpcPlugin = Join-Path $vcpkgRoot "installed\x64-windows\tools\grpc\grpc_cpp_plugin.exe"

if (-not (Test-Path $protoc)) {
    Write-Error "protoc not found at $protoc. Install via: vcpkg install protobuf:x64-windows"
    exit 1
}

if (-not (Test-Path $grpcPlugin)) {
    Write-Error "grpc_cpp_plugin not found at $grpcPlugin. Install via: vcpkg install grpc:x64-windows"
    exit 1
}

# Generate protobuf
Write-Host "Generating protobuf..."
& $protoc `
    --proto_path=$protoDir `
    --cpp_out=$outputDir `
    $protoFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "Protobuf generation failed"
    exit 1
}

# Generate gRPC
Write-Host "Generating gRPC..."
& $protoc `
    --proto_path=$protoDir `
    --grpc_out=$outputDir `
    --plugin=protoc-gen-grpc=$grpcPlugin `
    $protoFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "gRPC generation failed"
    exit 1
}

Write-Host "Proto generation complete!"
Write-Host "Output: $outputDir"
