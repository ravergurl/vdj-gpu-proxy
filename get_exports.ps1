$path = "C:\Users\peopl\AppData\Local\VirtualDJ\Drivers\ml1151.dll"
$bytes = [System.IO.File]::ReadAllBytes($path)
$text = [System.Text.Encoding]::ASCII.GetString($bytes)

# Regex for common ORT function patterns
$regex = "Ort[a-zA-Z0-9_]+"
$matches = [regex]::Matches($text, $regex) | Select-Object -ExpandProperty Value | Sort-Object | Unique

Write-Host "Found $($matches.Count) potential ORT exports:"
$matches | Out-File "ml1151_exports.txt"
$matches
