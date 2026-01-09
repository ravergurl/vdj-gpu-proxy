# End-to-End Binary Streaming Test
# Verifies complete binary streaming protocol works with remote server

param(
    [string]$VdjPath = "C:\Program Files\VirtualDJ",
    [int]$TestDuration = 45
)

$ErrorActionPreference = "Stop"

Write-Host "=== Binary Streaming End-to-End Test ===" -ForegroundColor Cyan
Write-Host ""

# Configuration
$dbgViewPath = "$PSScriptRoot\..\DebugView\Dbgview64a.exe"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "$PSScriptRoot\..\test_binary_e2e_$timestamp.log"
$vdjExe = Join-Path $VdjPath "virtualdj.exe"

# Pre-flight checks
Write-Host "1. Pre-flight Checks" -ForegroundColor Yellow
Write-Host "   Checking DLL installation..."

$dllLocations = @(
    "$VdjPath\onnxruntime.dll",
    "$env:LOCALAPPDATA\VirtualDJ\Drivers\ml1151.dll"
)

$allDllsOk = $true
foreach ($dll in $dllLocations) {
    if (Test-Path $dll) {
        $dllInfo = Get-Item $dll
        Write-Host "   ✓ $dll" -ForegroundColor Green
        Write-Host "     Size: $([math]::Round($dllInfo.Length / 1MB, 2)) MB, Modified: $($dllInfo.LastWriteTime)" -ForegroundColor Gray
    } else {
        Write-Host "   ✗ $dll NOT FOUND" -ForegroundColor Red
        $allDllsOk = $false
    }
}

if (-not $allDllsOk) {
    Write-Error "DLLs not installed correctly. Run scripts/install_proxy.ps1"
}

# Check registry config
Write-Host "`n   Checking registry configuration..."
$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (Test-Path $regPath) {
    $config = Get-ItemProperty -Path $regPath
    Write-Host "   ✓ TunnelUrl: $($config.TunnelUrl)" -ForegroundColor Green
    Write-Host "   ✓ Enabled: $($config.Enabled)" -ForegroundColor Green
} else {
    Write-Warning "Registry not configured"
}

# Check server health
Write-Host "`n   Checking server health..."
try {
    $health = Invoke-RestMethod -Uri "https://vdj-gpu-direct.ai-smith.net/health" -Method Get -TimeoutSec 5
    if ($health.status -eq "ok") {
        Write-Host "   ✓ Server is healthy" -ForegroundColor Green
    } else {
        Write-Warning "Server returned unexpected status: $($health.status)"
    }
} catch {
    Write-Warning "Server health check failed: $_"
    Write-Host "   Make sure server is running with HTTP streaming on port 8081" -ForegroundColor Yellow
}

Write-Host ""

# Find test track
Write-Host "2. Finding Test Track" -ForegroundColor Yellow
$testFile = Get-ChildItem -Path "$env:USERPROFILE\Music" -Filter "*.mp3" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $testFile) {
    Write-Error "No MP3 files found in Music folder"
}

Write-Host "   Using: $($testFile.Name)" -ForegroundColor Green
Write-Host ""

# Cleanup
Write-Host "3. Cleanup" -ForegroundColor Yellow
Get-Process | Where-Object { $_.ProcessName -like "*Dbgview*" -or $_.ProcessName -eq "virtualdj" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

if (Test-Path $logFile) {
    Remove-Item $logFile -Force
}

# Start DebugView
Write-Host "`n4. Starting DebugView" -ForegroundColor Yellow
$dbgProc = Start-Process -FilePath $dbgViewPath -ArgumentList "/accepteula","/l",$logFile,"/g","/t" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "   PID: $($dbgProc.Id)" -ForegroundColor Gray

# Start VirtualDJ
Write-Host "`n5. Starting VirtualDJ" -ForegroundColor Yellow
$vdjProc = Start-Process -FilePath $vdjExe -ArgumentList """$($testFile.FullName)""" -PassThru
Write-Host "   PID: $($vdjProc.Id)" -ForegroundColor Gray
Write-Host "   Waiting for initialization..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# Monitor for stems processing
Write-Host "`n6. Monitoring Stems Processing" -ForegroundColor Yellow
Write-Host "   Waiting $TestDuration seconds for automatic stems processing..." -ForegroundColor Gray
Write-Host "   (Or manually trigger stems in VDJ now)" -ForegroundColor Cyan

$elapsed = 0
$checkInterval = 5
while ($elapsed -lt $TestDuration) {
    Start-Sleep -Seconds $checkInterval
    $elapsed += $checkInterval

    # Check if VDJ crashed
    if (-not (Get-Process -Id $vdjProc.Id -ErrorAction SilentlyContinue)) {
        Write-Host "`n   ✗ VirtualDJ crashed!" -ForegroundColor Red
        break
    }

    Write-Host "   Elapsed: $elapsed / $TestDuration seconds" -ForegroundColor Gray
}

# Stop processes
Write-Host "`n7. Stopping Processes" -ForegroundColor Yellow
Stop-Process -Id $vdjProc.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $dbgProc.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Analyze results
Write-Host "`n=== Test Results ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $logFile)) {
    Write-Error "Log file not created"
}

$content = Get-Content $logFile -Raw

# Key indicators
$indicators = @{
    "Binary Protocol Used" = $content -match "RunInferenceBinary START"
    "Correct Endpoint" = $content -match "POST /inference_binary"
    "Connection Success" = $content -match "Connected!"
    "Audio Input Found" = $content -match "Found audio input"
    "Binary Response" = $content -match "Binary response status"
    "Success Status" = $content -match "Binary response status=0"
    "Parsed Outputs" = $content -match "Parsed \d+ binary outputs"
}

$passCount = 0
$failCount = 0

foreach ($key in $indicators.Keys) {
    if ($indicators[$key]) {
        Write-Host "✓ $key" -ForegroundColor Green
        $passCount++
    } else {
        Write-Host "✗ $key" -ForegroundColor Red
        $failCount++
    }
}

Write-Host ""
Write-Host "Results: $passCount passed, $failCount failed" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Yellow" })

# Show errors if any
$errors = Select-String -Path $logFile -Pattern "FAIL|ERROR|error|failed|crash" -CaseSensitive:$false

if ($errors) {
    Write-Host "`n=== Errors Found ===" -ForegroundColor Red
    $errors | Select-Object -First 10 | ForEach-Object {
        Write-Host $_.Line -ForegroundColor Red
    }
}

# Show key binary protocol messages
Write-Host "`n=== Key Binary Protocol Messages ===" -ForegroundColor Cyan
$binaryMessages = Select-String -Path $logFile -Pattern "RunInferenceBinary|Binary request|Binary response|Binary Output|Found audio" | Select-Object -First 30

if ($binaryMessages) {
    $binaryMessages | ForEach-Object {
        Write-Host $_.Line -ForegroundColor Gray
    }
} else {
    Write-Host "No binary protocol messages found!" -ForegroundColor Red
}

Write-Host "`nFull log: $logFile" -ForegroundColor Cyan
Write-Host ""

# Final verdict
if ($failCount -eq 0) {
    Write-Host "=== TEST PASSED ===" -ForegroundColor Green
    Write-Host "Binary streaming protocol is working correctly!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "=== TEST FAILED ===" -ForegroundColor Red
    Write-Host "Review errors above and check:" -ForegroundColor Yellow
    Write-Host "1. Server is updated with latest code (commit a7d2ff7)" -ForegroundColor Yellow
    Write-Host "2. Server is running on port 8081 (HTTP streaming)" -ForegroundColor Yellow
    Write-Host "3. Cloudflare tunnel is routing to port 8081" -ForegroundColor Yellow
    exit 1
}
