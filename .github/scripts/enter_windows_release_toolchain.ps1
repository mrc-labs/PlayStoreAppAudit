New-Item -ItemType Directory -Force toolchain-delta-evidence | Out-Null
$ErrorActionPreference = 'Stop'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$inventory = & $vswhere -all -products '*' -format json | ConvertFrom-Json
$inventory | ConvertTo-Json -Depth 8 | Set-Content toolchain-delta-evidence/visual-studio-inventory.json
$arch = if ($env:PACKAGE_ARCH -eq 'arm64') { 'arm64' } else { 'x64' }
$selected = $null
$available = @()
foreach ($installation in $inventory) {
  if ($installation.isPrerelease -or $installation.channelId -notin @('VisualStudio.18.Stable', 'VisualStudio.18.Release')) { continue }
  $tools = Join-Path $installation.installationPath 'VC/Tools/MSVC'
  if (-not (Test-Path -LiteralPath $tools)) { continue }
  foreach ($version in (Get-ChildItem -LiteralPath $tools -Directory | Sort-Object { [version]$_.Name } -Descending)) {
    $compiler = Join-Path $version.FullName "bin/Host$arch/$arch/cl.exe"
    $available += @{ toolset = $version.Name; compiler = $compiler; exists = (Test-Path -LiteralPath $compiler) }
    if (-not $selected -and $version.Name -like '14.52.*' -and (Test-Path -LiteralPath $compiler)) { $selected = $installation.installationPath }
  }
}
$available | ConvertTo-Json -Depth 4 | Set-Content toolchain-delta-evidence/native-toolsets.json
if (-not $selected) {
  # Both native hosted pools may still supply18.11/14.51. Provision only
  # current stable native Build Tools in this ephemeral diagnostic runner.
  $channelPath = Join-Path $env:RUNNER_TEMP 'psaa-vs18-release-channel.json'
  Invoke-WebRequest 'https://aka.ms/vs/stable/channel' -OutFile $channelPath
  $channel = Get-Content -Raw -LiteralPath $channelPath | ConvertFrom-Json
  $product = @($channel.channelItems | Where-Object { $_.id -eq 'Microsoft.VisualStudio.Product.BuildTools' })
  if ($product.Count -ne 1 -or $product[0].version -notlike '18.12.*') { throw 'Unreviewed stable VS release channel.' }
  $setup = @($channel.channelItems | Where-Object { $_.id -eq 'VisualStudio.18.Release.Bootstrappers.Setup' })
  $payload = @($setup.payloads | Where-Object { $_.fileName -eq 'vs_Setup.exe' })
  if ($payload.Count -ne 1 -or $payload[0].url -notlike 'https://download.visualstudio.microsoft.com/*') { throw 'Unqualified official installer provenance.' }
  $bootstrapper = Join-Path $env:RUNNER_TEMP 'psaa-vs-buildtools.exe'
  Invoke-WebRequest $payload[0].url -OutFile $bootstrapper
  $digest = (Get-FileHash -LiteralPath $bootstrapper -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($digest -ne $payload[0].sha256.ToLowerInvariant()) { throw 'Official installer hash mismatch.' }
  $signature = Get-AuthenticodeSignature -LiteralPath $bootstrapper
  if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'Official installer signature invalid.' }
  Copy-Item -LiteralPath $channelPath -Destination toolchain-delta-evidence/vs-release-channel.json
  @{ url = $payload[0].url; sha256 = $digest; product_version = $product[0].version; signer = $signature.SignerCertificate.Subject; scope = 'Ephemeral host Build Tools only; no production signing' } | ConvertTo-Json | Set-Content toolchain-delta-evidence/vs-bootstrapper-provenance.json
  $install = Join-Path $env:RUNNER_TEMP 'psaa-native-msvc'
  $component = if ($arch -eq 'arm64') { 'Microsoft.VisualStudio.Component.VC.Tools.ARM64' } else { 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64' }
  $arguments = @('--quiet', '--wait', '--norestart', '--nocache', '--productId', 'Microsoft.VisualStudio.Product.BuildTools', '--channelId', 'VisualStudio.18.Release', '--channelUri', 'https://aka.ms/vs/stable/channel', '--installPath', $install, '--add', $component, '--add', 'Microsoft.VisualStudio.Component.Windows11SDK.26100')
  $process = Start-Process -FilePath $bootstrapper -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
  if ($process.ExitCode -notin @(0, 3010)) { throw "Stable Build Tools installation failed: $($process.ExitCode)" }
  $selected = $install
}
if (-not $selected) { throw 'BLOCKER: native stable MSVC14.52 unavailable; no parser rebuild started.' }
Import-Module (Join-Path $selected 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $selected -SkipAutomaticLocation -DevCmdArguments "-arch=$arch -host_arch=$arch -vcvars_ver=14.52"
if ($env:VSCMD_ARG_HOST_ARCH -ne $arch -or $env:VSCMD_ARG_TGT_ARCH -ne $arch) { throw 'Native host/target required.' }
$nativeCompilers = @(Get-ChildItem -LiteralPath (Join-Path $selected 'VC/Tools/MSVC') -Directory | Where-Object { $_.Name -like '14.52.*' } | ForEach-Object { Join-Path $_.FullName "bin/Host$arch/$arch/cl.exe" })
$nativeCompilers | ForEach-Object { @{ path = $_; exists = (Test-Path -LiteralPath $_) } } | ConvertTo-Json | Set-Content toolchain-delta-evidence/native-compiler-after-setup.json
$nativeCompiler = @($nativeCompilers | Where-Object { Test-Path -LiteralPath $_ })
if ($nativeCompiler.Count -ne 1) { throw 'Native14.52 compiler payload missing after setup; no runtime build started.' }
$env:PATH = (Split-Path -Parent $nativeCompiler[0]) + ';' + $env:PATH

foreach ($taskKey in @('VSINSTALLDIR','VCINSTALLDIR','VCToolsInstallDir','VCToolsVersion','WindowsSdkDir','WindowsSDKVersion','WindowsSDKLibVersion','UniversalCRTSdkDir','UCRTVersion','VSCMD_ARG_HOST_ARCH','VSCMD_ARG_TGT_ARCH','VSCMD_VER','INCLUDE','LIB','LIBPATH','PATH')) {
    $taskValue = [Environment]::GetEnvironmentVariable($taskKey)
    if ($taskValue) { "$taskKey=$taskValue" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8 }
}
