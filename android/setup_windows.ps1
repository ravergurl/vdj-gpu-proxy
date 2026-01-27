# VDJ Stems - Android Phone Setup (Windows side)
# Run this after setting up Termux on your phone

param(
    [switch]$Push,      # Push files to phone
    [switch]$Forward,   # Setup port forwarding
    [switch]$Test,      # Test connection
    [switch]$Configure  # Configure VDJ proxy registry
)

$ErrorActionPreference = "Stop"

function Test-AdbDevice {
    $devices = adb devices 2>&1
    if ($devices -notmatch "device$") {
        Write-Error "No Android device connected. Enable USB debugging and connect phone."
        exit 1
    }
    Write-Host "Device connected" -ForegroundColor Green
}

function Push-Files {
    Write-Host "Pushing files to phone..." -ForegroundColor Cyan
    Test-AdbDevice

    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    if (-not $scriptDir) { $scriptDir = "." }

    adb push "$scriptDir/setup_termux.sh" /sdcard/vdj_setup_termux.sh
    adb push "$scriptDir/termux_server.py" /sdcard/vdj_termux_server.py

    Write-Host @"

Files pushed to /sdcard/
Now open Termux and run:

  cp /sdcard/vdj_setup_termux.sh ~/
  cp /sdcard/vdj_termux_server.py ~/vdj-stems/termux_server.py
  chmod +x ~/vdj_setup_termux.sh
  ~/vdj_setup_termux.sh

"@ -ForegroundColor Yellow
}

function Setup-PortForward {
    Write-Host "Setting up ADB port forwarding..." -ForegroundColor Cyan
    Test-AdbDevice

    # Forward port 8081
    adb forward tcp:8081 tcp:8081

    Write-Host "Port 8081 forwarded: localhost:8081 -> phone:8081" -ForegroundColor Green
    Write-Host "Keep this terminal open to maintain forwarding" -ForegroundColor Yellow
}

function Test-Connection {
    Write-Host "Testing connection to phone server..." -ForegroundColor Cyan

    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8081/health" -UseBasicParsing -TimeoutSec 5
        $json = $response.Content | ConvertFrom-Json

        if ($json.status -eq "ok") {
            Write-Host "Connection successful!" -ForegroundColor Green
            Write-Host "Server is running on phone" -ForegroundColor Green
        } else {
            Write-Host "Unexpected response: $($response.Content)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Connection failed: $_" -ForegroundColor Red
        Write-Host @"

Checklist:
1. Is Termux running the server? (python termux_server.py)
2. Is port forwarding active? (adb forward tcp:8081 tcp:8081)
3. Is USB debugging enabled?
"@ -ForegroundColor Yellow
    }
}

function Configure-Registry {
    Write-Host "Configuring VDJ proxy to use phone server..." -ForegroundColor Cyan

    $regPath = "HKCU:\Software\VDJ-GPU-Proxy"

    # Create key if not exists
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force | Out-Null
    }

    # Set values for localhost (ADB forwarded)
    Set-ItemProperty -Path $regPath -Name "ServerAddress" -Value "127.0.0.1" -Type String
    Set-ItemProperty -Path $regPath -Name "ServerPort" -Value 8081 -Type DWord
    Set-ItemProperty -Path $regPath -Name "Enabled" -Value 1 -Type DWord

    # Clear tunnel URL (use direct connection)
    Remove-ItemProperty -Path $regPath -Name "TunnelUrl" -ErrorAction SilentlyContinue

    Write-Host "Registry configured:" -ForegroundColor Green
    Write-Host "  ServerAddress: 127.0.0.1"
    Write-Host "  ServerPort: 8081"
    Write-Host "  Enabled: 1"
}

# Main
if (-not ($Push -or $Forward -or $Test -or $Configure)) {
    Write-Host @"
VDJ Stems - Android Phone Setup

Usage:
  .\setup_windows.ps1 -Push       # Push files to phone
  .\setup_windows.ps1 -Forward    # Setup ADB port forwarding
  .\setup_windows.ps1 -Test       # Test connection to phone
  .\setup_windows.ps1 -Configure  # Configure VDJ proxy registry

Typical workflow:
  1. .\setup_windows.ps1 -Push
  2. (Run setup in Termux on phone)
  3. (Start server in Termux: python termux_server.py)
  4. .\setup_windows.ps1 -Forward
  5. .\setup_windows.ps1 -Test
  6. .\setup_windows.ps1 -Configure
  7. Launch VirtualDJ

"@
    exit 0
}

if ($Push) { Push-Files }
if ($Forward) { Setup-PortForward }
if ($Test) { Test-Connection }
if ($Configure) { Configure-Registry }
