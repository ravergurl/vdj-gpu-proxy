#Requires -Version 5.1
param(
    [Parameter(Position=0)]
    [ValidateSet("status", "enable", "disable", "config", "logs", "test", "help")]
    [string]$Command = "help",
    
    [string]$ServerAddress,
    [int]$ServerPort,
    [string]$LogLevel
)

$ErrorActionPreference = "Stop"
$RegPath = "HKCU:\Software\VDJ-GPU-Proxy"
$LogDir = "$env:LOCALAPPDATA\VDJ-GPU-Proxy"

function Get-ProxyConfig {
    if (-not (Test-Path $RegPath)) {
        return @{
            Enabled = $false
            ServerAddress = "127.0.0.1"
            ServerPort = 50051
        }
    }
    
    return @{
        Enabled = (Get-ItemProperty -Path $RegPath -Name "Enabled" -ErrorAction SilentlyContinue).Enabled -eq 1
        ServerAddress = (Get-ItemProperty -Path $RegPath -Name "ServerAddress" -ErrorAction SilentlyContinue).ServerAddress
        ServerPort = (Get-ItemProperty -Path $RegPath -Name "ServerPort" -ErrorAction SilentlyContinue).ServerPort
    }
}

function Show-Status {
    $config = Get-ProxyConfig
    
    Write-Host ""
    Write-Host "VDJ-GPU-Proxy Status" -ForegroundColor Cyan
    Write-Host "====================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Enabled:        " -NoNewline
    if ($config.Enabled) {
        Write-Host "YES" -ForegroundColor Green
    } else {
        Write-Host "NO" -ForegroundColor Red
    }
    Write-Host "Server Address: $($config.ServerAddress)"
    Write-Host "Server Port:    $($config.ServerPort)"
    Write-Host ""
    
    $vdjPath = Get-VdjPath
    if ($vdjPath) {
        Write-Host "VirtualDJ Path: $vdjPath" -ForegroundColor Gray
        $proxyInstalled = Test-Path (Join-Path $vdjPath "onnxruntime_real.dll")
        Write-Host "Proxy Installed:" -NoNewline
        if ($proxyInstalled) {
            Write-Host " YES" -ForegroundColor Green
        } else {
            Write-Host " NO" -ForegroundColor Yellow
        }
    }
    
    Write-Host ""
    Write-Host "Server Connection Test:" -NoNewline
    $result = Test-ServerConnection $config.ServerAddress $config.ServerPort
    if ($result) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAILED" -ForegroundColor Red
    }
    Write-Host ""
}

function Get-VdjPath {
    $paths = @(
        "$env:ProgramFiles\VirtualDJ",
        "${env:ProgramFiles(x86)}\VirtualDJ",
        "$env:LOCALAPPDATA\VirtualDJ"
    )
    
    foreach ($path in $paths) {
        if (Test-Path (Join-Path $path "VirtualDJ.exe")) {
            return $path
        }
    }
    return $null
}

function Test-ServerConnection($address, $port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $result = $client.BeginConnect($address, $port, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne(2000, $false)
        $client.Close()
        return $success
    } catch {
        return $false
    }
}

function Enable-Proxy {
    if (-not (Test-Path $RegPath)) {
        New-Item -Path $RegPath -Force | Out-Null
    }
    Set-ItemProperty -Path $RegPath -Name "Enabled" -Value 1
    Write-Host "Proxy ENABLED" -ForegroundColor Green
}

function Disable-Proxy {
    if (Test-Path $RegPath) {
        Set-ItemProperty -Path $RegPath -Name "Enabled" -Value 0
    }
    Write-Host "Proxy DISABLED" -ForegroundColor Yellow
}

function Set-Config {
    if (-not (Test-Path $RegPath)) {
        New-Item -Path $RegPath -Force | Out-Null
    }
    
    if ($ServerAddress) {
        Set-ItemProperty -Path $RegPath -Name "ServerAddress" -Value $ServerAddress
        Write-Host "Server address set to: $ServerAddress"
    }
    
    if ($ServerPort -gt 0) {
        Set-ItemProperty -Path $RegPath -Name "ServerPort" -Value $ServerPort
        Write-Host "Server port set to: $ServerPort"
    }
    
    if (-not $ServerAddress -and $ServerPort -le 0) {
        Show-Status
    }
}

function Show-Logs {
    if (-not (Test-Path $LogDir)) {
        Write-Host "No log directory found at $LogDir" -ForegroundColor Yellow
        return
    }
    
    $logs = Get-ChildItem -Path $LogDir -Filter "*.log" | Sort-Object LastWriteTime -Descending
    
    if ($logs.Count -eq 0) {
        Write-Host "No log files found" -ForegroundColor Yellow
        return
    }
    
    $latest = $logs[0]
    Write-Host "Showing latest log: $($latest.Name)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Get-Content $latest.FullName -Tail 50
}

function Test-Proxy {
    $config = Get-ProxyConfig
    
    Write-Host "Testing proxy connection..." -ForegroundColor Cyan
    Write-Host ""
    
    if (-not $config.Enabled) {
        Write-Host "WARNING: Proxy is disabled" -ForegroundColor Yellow
    }
    
    Write-Host "Connecting to $($config.ServerAddress):$($config.ServerPort)..."
    
    if (Test-ServerConnection $config.ServerAddress $config.ServerPort) {
        Write-Host "SUCCESS: Server is reachable" -ForegroundColor Green
    } else {
        Write-Host "FAILED: Cannot connect to server" -ForegroundColor Red
        Write-Host ""
        Write-Host "Troubleshooting:" -ForegroundColor Yellow
        Write-Host "  1. Ensure GPU server is running: vdj-stems-server --host 0.0.0.0"
        Write-Host "  2. Check firewall allows port $($config.ServerPort)"
        Write-Host "  3. Verify server address is correct"
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "VDJ-GPU-Proxy Control Tool" -ForegroundColor Cyan
    Write-Host "==========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: vdj-proxy-ctl.ps1 <command> [options]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  status    Show current proxy status and configuration"
    Write-Host "  enable    Enable the proxy"
    Write-Host "  disable   Disable the proxy (falls back to local inference)"
    Write-Host "  config    Set configuration options"
    Write-Host "  logs      Show recent log entries"
    Write-Host "  test      Test connection to GPU server"
    Write-Host "  help      Show this help message"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -ServerAddress <ip>   Set GPU server IP/hostname"
    Write-Host "  -ServerPort <port>    Set GPU server port (default: 50051)"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\vdj-proxy-ctl.ps1 status"
    Write-Host "  .\vdj-proxy-ctl.ps1 config -ServerAddress 192.168.1.100"
    Write-Host "  .\vdj-proxy-ctl.ps1 enable"
    Write-Host "  .\vdj-proxy-ctl.ps1 test"
    Write-Host ""
}

switch ($Command) {
    "status"  { Show-Status }
    "enable"  { Enable-Proxy }
    "disable" { Disable-Proxy }
    "config"  { Set-Config }
    "logs"    { Show-Logs }
    "test"    { Test-Proxy }
    "help"    { Show-Help }
    default   { Show-Help }
}
