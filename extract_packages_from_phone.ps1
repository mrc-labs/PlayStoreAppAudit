param(
    [string]$AdbPath = ".\platform-tools\adb.exe",
    [string]$OutputFile = ".\packages_from_phone.csv",
    [switch]$IncludeSystemApps
)

if (-not (Test-Path $AdbPath)) {
    $command = Get-Command adb -ErrorAction SilentlyContinue
    if ($command) {
        $AdbPath = $command.Source
    } else {
        throw "ADB non trovato. Installa Android SDK Platform-Tools."
    }
}

& $AdbPath devices

$arguments = @("shell", "pm", "list", "packages")
if (-not $IncludeSystemApps) {
    $arguments += "-3"
}

$packages = & $AdbPath @arguments |
    ForEach-Object { $_ -replace "^package:", "" } |
    Where-Object { $_ -match "\." } |
    Sort-Object -Unique

"app_name,package_name" | Set-Content -Path $OutputFile -Encoding UTF8
$packages | ForEach-Object {
    ',"{0}"' -f ($_ -replace '"', '""')
} | Add-Content -Path $OutputFile -Encoding UTF8

Write-Host "Create $($packages.Count) righe in $OutputFile"
