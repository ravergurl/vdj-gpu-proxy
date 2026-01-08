$ErrorActionPreference = 'Stop'
$reg = 'HKCU:\Software\VDJ-GPU-Proxy'
$url = 'https://programming-msgstr-need-resolved.trycloudflare.com'

Write-Host "Updating TunnelUrl to: $url"
Set-ItemProperty $reg 'TunnelUrl' $url
Set-ItemProperty $reg 'Enabled' 1

Write-Host "Success!"
