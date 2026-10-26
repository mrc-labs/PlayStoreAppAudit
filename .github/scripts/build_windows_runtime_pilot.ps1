param([Parameter(Mandatory = $true)][string]$WorkRoot, [switch]$PrerequisitesOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:RUNNER_ARCH -ne 'X64' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'Only native Windows x64 is authorized.'
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
# Qt 6.12 / PySide require MSVC 2022; select its maintained v143 toolset explicitly.
$evidence = Join-Path (Get-Location) 'windows-pilot-evidence'
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
& $vswhere -all -products '*' -format json | Set-Content (Join-Path $evidence 'visual-studio-inventory.json')
# Hosted VS 2026 contains the supported VS 2022 compiler as a side-by-side component.
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.14.44.17.14.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $vs) { throw 'Supported MSVC 2022 x64 toolset unavailable.' }
Import-Module (Join-Path $vs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64 -vcvars_ver=14.44'
if ($env:VSCMD_ARG_HOST_ARCH -ne 'x64' -or $env:VSCMD_ARG_TGT_ARCH -ne 'x64') { throw 'MSVC must be native x64.' }
$env:PILOT_VS_PATH = $vs
$pilotArguments = @('.github/scripts/build_windows_runtime_pilot.py', '--work-root', $WorkRoot)
if ($PrerequisitesOnly) { $pilotArguments += '--prerequisites-only' }
python @pilotArguments
if ($LASTEXITCODE -ne 0) { throw 'Windows diagnostic source-stack pilot failed.' }
