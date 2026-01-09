# VDJ GPU Proxy - Cloudflare Tunnel Configuration
# Run as Administrator to configure registry

param(
    [string]$TunnelUrl = "https://vdj-gpu-direct.ai-smith.net",
    [switch]$Disable,
    [switch]$ShowConfig
)

$regPath = "HKCU:\Software\VDJ-GPU-Proxy"

if ($ShowConfig) {
    Write-Host "Current VDJ GPU Proxy Configuration:" -ForegroundColor Cyan
    Write-Host "=====================================" -ForegroundColor Cyan

    if (Test-Path $regPath) {
        $props = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
        Write-Host "TunnelUrl:      $($props.TunnelUrl)"
        Write-Host "ServerAddress:  $($props.ServerAddress)"
        Write-Host "ServerPort:     $($props.ServerPort)"
        Write-Host "Enabled:        $($props.Enabled)"
    } else {
        Write-Host "No configuration found (using defaults)"
    }
    exit 0
}

# Create registry key if it doesn't exist
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
    Write-Host "Created registry key: $regPath" -ForegroundColor Green
}

if ($Disable) {
    Set-ItemProperty -Path $regPath -Name "Enabled" -Value 0 -Type DWord
    Write-Host "VDJ GPU Proxy disabled" -ForegroundColor Yellow
} else {
    # Set tunnel URL
    Set-ItemProperty -Path $regPath -Name "TunnelUrl" -Value $TunnelUrl -Type String
    Set-ItemProperty -Path $regPath -Name "Enabled" -Value 1 -Type DWord

    Write-Host "VDJ GPU Proxy configured:" -ForegroundColor Green
    Write-Host "  Tunnel URL: $TunnelUrl"
    Write-Host "  Enabled:    Yes"
}

Write-Host ""
Write-Host "To test, restart VirtualDJ and check for stems separation." -ForegroundColor Cyan
Write-Host "Debug output can be viewed with DebugView or similar tool." -ForegroundColor DarkGray
