param([Parameter(Mandatory = $true)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:RUNNER_ARCH -ne 'ARM64' -or $env:PROCESSOR_ARCHITECTURE -ne 'ARM64') {
    throw 'Only a native Windows ARM64 runner is authorized.'
}
$evidence = Join-Path (Get-Location) 'windows-arm64-pilot-evidence'
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$inventory = & $vswhere -all -products '*' -format json
if ($LASTEXITCODE -ne 0) { throw 'Visual Studio inventory failed.' }
$inventory | Set-Content (Join-Path $evidence 'visual-studio-inventory.json')
$selected = $null
$available = @()
foreach ($installation in ($inventory | ConvertFrom-Json)) {
    $tools = Join-Path $installation.installationPath 'VC/Tools/MSVC'
    if (-not (Test-Path -LiteralPath $tools)) { continue }
    foreach ($version in (Get-ChildItem -LiteralPath $tools -Directory)) {
        $compiler = Join-Path $version.FullName 'bin/Hostarm64/arm64/cl.exe'
        $available += @{ installation = $installation.installationPath; toolset = $version.Name; native_compiler = $compiler; exists = (Test-Path -LiteralPath $compiler) }
        if ($version.Name -like '14.44.*' -and (Test-Path -LiteralPath $compiler)) { $selected = $installation.installationPath }
    }
}
$available | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $evidence 'native-toolsets.json')
if (-not $selected) { throw 'BLOCKER: supported v143 14.44 native ARM64 host/target compiler unavailable; no source rebuild started.' }
Import-Module (Join-Path $selected 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $selected -SkipAutomaticLocation -DevCmdArguments '-arch=arm64 -host_arch=arm64 -vcvars_ver=14.44'
if ($env:VSCMD_ARG_HOST_ARCH -ne 'arm64' -or $env:VSCMD_ARG_TGT_ARCH -ne 'arm64') { throw 'MSVC host and target must both be ARM64.' }
$env:PILOT_VS_PATH = $selected
python .github/scripts/probe_windows_arm64_runtime.py --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) { throw 'ARM64 prerequisites failed; no full rebuild authorized by this result.' }
