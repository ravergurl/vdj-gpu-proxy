$commands = @"
Get-Service | Where-Object {$_.Name -like '*rustdesk*' -or $_.DisplayName -like '*RustDesk*'}
Get-Process | Where-Object {$_.Name -like '*rustdesk*'}
Get-ItemProperty -Path 'HKLM:\SOFTWARE\RustDesk\*','HKCU:\SOFTWARE\RustDesk\*' -ErrorAction SilentlyContinue
Get-Content "$env:APPDATA\RustDesk\config\RustDesk.toml" -ErrorAction SilentlyContinue
Get-Content "$env:APPDATA\RustDesk\RustDesk.toml" -ErrorAction SilentlyContinue
netstat -ano | Select-String '21115|21116|21117|21118|21119'
rustdesk --get-id
"@

Write-Host "=== Remote Server Discovery Commands ==="
Write-Host $commands
Write-Host "`n=== Copy these commands to run on RDP session ==="
