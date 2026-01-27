# Test Binary Streaming Protocol - Automated Debugging
# Captures VDJ debug output to diagnose crash

param(
    [string]$VdjPath = "C:\Program Files\VirtualDJ",
    [string]$TestTrack = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=== VDJ Binary Streaming Test ===" -ForegroundColor Cyan
Write-Host ""

# Find DebugView
$dbgViewPath = "$PSScriptRoot\..\DebugView\Dbgview64a.exe"
if (-not (Test-Path $dbgViewPath)) {
    Write-Error "DebugView not found at $dbgViewPath"
    exit 1
}

# Output file for logs
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "$PSScriptRoot\..\vdj_test_$timestamp.log"

Write-Host "1. Starting DebugView..." -ForegroundColor Yellow
# Start DebugView with logging enabled
$dbgView = Start-Process -FilePath $dbgViewPath `
    -ArgumentList "/l", $logFile, "/t" `
    -PassThru `
    -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "2. DebugView running (PID: $($dbgView.Id))" -ForegroundColor Green
Write-Host "   Log file: $logFile" -ForegroundColor Gray
Write-Host ""

# Check if VDJ is already running
$vdjProcess = Get-Process virtualdj -ErrorAction SilentlyContinue
if ($vdjProcess) {
    Write-Host "3. VirtualDJ already running (PID: $($vdjProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "3. Starting VirtualDJ..." -ForegroundColor Yellow
    $vdjExe = Join-Path $VdjPath "virtualdj.exe"

    if (-not (Test-Path $vdjExe)) {
        Write-Error "VirtualDJ not found at $vdjExe"
        Stop-Process -Id $dbgView.Id -Force
        exit 1
    }

    $vdjProcess = Start-Process -FilePath $vdjExe -PassThru
    Write-Host "   VirtualDJ started (PID: $($vdjProcess.Id))" -ForegroundColor Green

    # Give VDJ time to initialize
    Write-Host "   Waiting for initialization..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}

Write-Host ""
Write-Host "=== Manual Test Instructions ===" -ForegroundColor Cyan
Write-Host "1. Load a track in VirtualDJ"
Write-Host "2. Click on stems or waveform to trigger separation"
Write-Host "3. Watch for crash or error"
Write-Host "4. Press ENTER when done testing"
Write-Host ""

# Wait for user to test
Read-Host "Press ENTER after testing stems"

Write-Host ""
Write-Host "=== Capturing Logs ===" -ForegroundColor Cyan

# Stop DebugView to flush logs
Stop-Process -Id $dbgView.Id -Force
Start-Sleep -Seconds 2

# Check if log file exists and has content
if (Test-Path $logFile) {
    $logContent = Get-Content $logFile -Raw

    if ($logContent) {
        Write-Host "Log captured successfully ($([math]::Round((Get-Item $logFile).Length / 1KB, 2)) KB)" -ForegroundColor Green
        Write-Host ""

        # Search for key patterns
        Write-Host "=== Key Debug Messages ===" -ForegroundColor Cyan

        # Connection messages
        $connectionLines = Select-String -Path $logFile -Pattern "VDJ-GPU-Proxy: Connect|HTTP: Connect|TunnelUrl" | Select-Object -First 10
        if ($connectionLines) {
            Write-Host "`n[Connection]" -ForegroundColor Yellow
            $connectionLines | ForEach-Object { Write-Host $_.Line -ForegroundColor Gray }
        }

        # Binary protocol messages
        $binaryLines = Select-String -Path $logFile -Pattern "RunInferenceBinary|Binary request|Binary response|Binary Output" | Select-Object -First 20
        if ($binaryLines) {
            Write-Host "`n[Binary Protocol]" -ForegroundColor Yellow
            $binaryLines | ForEach-Object { Write-Host $_.Line -ForegroundColor Gray }
        }

        # Error messages
        $errorLines = Select-String -Path $logFile -Pattern "FAIL|ERROR|error|failed|crash|exception" -CaseSensitive:$false | Select-Object -First 20
        if ($errorLines) {
            Write-Host "`n[Errors]" -ForegroundColor Red
            $errorLines | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
        }

        # Success indicators
        $successLines = Select-String -Path $logFile -Pattern "success=true|OK|Connected|Parsed.*outputs" | Select-Object -First 10
        if ($successLines) {
            Write-Host "`n[Success]" -ForegroundColor Green
            $successLines | ForEach-Object { Write-Host $_.Line -ForegroundColor Gray }
        }

        Write-Host ""
        Write-Host "Full log saved to: $logFile" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "To view full log: notepad `"$logFile`"" -ForegroundColor Gray
    } else {
        Write-Warning "Log file is empty - no debug output captured"
        Write-Host "Make sure VDJ proxy DLL is installed and enabled" -ForegroundColor Yellow
    }
} else {
    Write-Warning "Log file not created"
}

Write-Host ""
Write-Host "=== Registry Configuration ===" -ForegroundColor Cyan
$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (Test-Path $regPath) {
    Get-ItemProperty -Path $regPath | Format-List TunnelUrl, ServerAddress, ServerPort, Enabled
} else {
    Write-Warning "Registry configuration not found"
}

Write-Host ""
Write-Host "Test complete. Analyze the log above for root cause." -ForegroundColor Green
