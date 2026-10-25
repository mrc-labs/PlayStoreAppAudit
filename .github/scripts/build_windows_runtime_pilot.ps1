param([Parameter(Mandatory = $true)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:RUNNER_ARCH -ne 'X64' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'Only native Windows x64 is authorized.'
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
# Qt 6.12 / PySide require MSVC 2022; select its maintained v143 toolset explicitly.
$vs = & $vswhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $vs) { throw 'Supported MSVC 2022 x64 toolset unavailable.' }
Import-Module (Join-Path $vs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
if ($env:VSCMD_ARG_HOST_ARCH -ne 'x64' -or $env:VSCMD_ARG_TGT_ARCH -ne 'x64') { throw 'MSVC must be native x64.' }
$env:PILOT_VS_PATH = $vs
python .github/scripts/build_windows_runtime_pilot.py --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) { throw 'Windows diagnostic source-stack pilot failed.' }
