param(
    [Parameter(Mandatory = $true)]
    [string]$WorkRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:RUNNER_ARCH -ne 'ARM64') { throw 'OpenSSL requires a native ARM64 runner.' }
python -c "import platform, struct, sysconfig; assert platform.machine().upper() == 'ARM64'; assert struct.calcsize('P') == 8; assert not sysconfig.get_config_var('Py_GIL_DISABLED')"
if ($LASTEXITCODE -ne 0) { throw 'OpenSSL requires native GIL-enabled ARM64 Python.' }
if (Test-Path -LiteralPath $WorkRoot) { throw 'OpenSSL work root must be fresh.' }
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
$evidence = Join-Path $WorkRoot 'evidence'
New-Item -ItemType Directory -Path $evidence | Out-Null

rustup toolchain install 1.99.1 --profile minimal
if ($LASTEXITCODE -ne 0) { throw 'Could not install audited Rust 1.99.1.' }
rustup default 1.99.1
if ($LASTEXITCODE -ne 0) { throw 'Could not select audited Rust 1.99.1.' }
$rust = rustc -vV
if ($LASTEXITCODE -ne 0 -or $rust -notcontains 'host: aarch64-pc-windows-msvc' -or
    $rust -notcontains 'release: 1.99.1') { throw 'Rust must be native ARM64 MSVC 1.99.1.' }
$rust | Set-Content -LiteralPath (Join-Path $evidence 'rust.txt')

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.ARM64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $vs) { throw 'Native ARM64 Visual Studio tools are missing.' }
Import-Module (Join-Path $vs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=arm64 -host_arch=arm64'
if ($env:VSCMD_ARG_HOST_ARCH -ne 'arm64' -or $env:VSCMD_ARG_TGT_ARCH -ne 'arm64') {
    throw 'MSVC host and target must both be ARM64.'
}
$compiler = (Get-Command cl.exe).Source
python .github/scripts/inspect_pe.py --expect 0xAA64 $compiler
if ($LASTEXITCODE -ne 0) { throw 'MSVC compiler is not a native ARM64 PE.' }
$linker = (Get-Command link.exe).Source
python .github/scripts/inspect_pe.py --expect 0xAA64 $linker
if ($LASTEXITCODE -ne 0) { throw 'MSVC linker is not a native ARM64 PE.' }
# OpenSSL's documented CLANGASM target uses clang-cl only for ARM64 assembly.
$clang = (Get-Command clang-cl.exe).Source
python .github/scripts/inspect_pe.py --expect 0xAA64 $clang
if ($LASTEXITCODE -ne 0) { throw 'OpenSSL assembler must be native ARM64 clang-cl.' }
& $clang --version | Set-Content -LiteralPath (Join-Path $evidence 'clang.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect clang-cl.' }
perl -v | Set-Content -LiteralPath (Join-Path $evidence 'perl.txt')
if ($LASTEXITCODE -ne 0) { throw 'The supported native Windows Perl prerequisite is missing.' }

$version = '4.0.3'
$url = "https://github.com/openssl/openssl/releases/download/openssl-$version/openssl-$version.tar.gz"
$sha256 = '325b5c806167c13b40b1ffeadfe0248197c00eccc4cf123ec1e28d2d2fd216d9'
$archive = Join-Path $evidence "openssl-$version.tar.gz"
Invoke-WebRequest -Uri $url -OutFile $archive
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha256) {
    throw 'Official OpenSSL source SHA-256 mismatch.'
}
python -c "import pathlib,sys,tarfile; archive,root=sys.argv[1:]; t=tarfile.open(archive); assert all(p.name.startswith('openssl-4.0.3/') or p.name == 'openssl-4.0.3' for p in t.getmembers()); t.extractall(root,filter='data')" $archive $WorkRoot
if ($LASTEXITCODE -ne 0) { throw 'Safe OpenSSL source extraction failed.' }
$source = Join-Path $WorkRoot "openssl-$version"
$prefix = Join-Path $WorkRoot 'installed'
$target = 'VC-WIN64-CLANGASM-ARM'
$configure = @($target, 'no-shared', 'no-module', 'no-tests', 'no-docs',
    'no-makedepend', "--prefix=$prefix", '--libdir=lib',
    '--openssldir=C:/Program Files/Common Files/SSL', 'CFLAGS=/MD')
Push-Location -LiteralPath $source
try {
    & perl Configure @configure 2>&1 | Tee-Object -FilePath (Join-Path $evidence 'configure.log')
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL ARM64 configuration failed.' }
    $makefile = Get-Content -LiteralPath 'makefile' -Raw
    if ($makefile -notmatch '(?m)^CFLAGS=.* /MD\s*$' -and $makefile -notmatch '(?m)^CFLAGS=/MD\s*$') {
        throw 'OpenSSL must use the explicit dynamic CRT /MD compiler override.'
    }
    Copy-Item -LiteralPath 'makefile' -Destination (Join-Path $evidence 'makefile')
    & nmake 2>&1 | Tee-Object -FilePath (Join-Path $evidence 'build.log')
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL native build failed.' }
    & nmake install_sw 2>&1 | Tee-Object -FilePath (Join-Path $evidence 'install.log')
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL isolated installation failed.' }
} finally {
    Pop-Location
}

$lib = Join-Path $prefix 'lib'
$tool = Join-Path $prefix 'bin/openssl.exe'
foreach ($required in @('lib/libcrypto.lib', 'lib/libssl.lib', 'include/openssl/opensslv.h', 'bin/openssl.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $prefix $required) -PathType Leaf)) {
        throw "Incomplete OpenSSL installation: $required"
    }
}
if (@(Get-ChildItem -LiteralPath $prefix -Recurse -Filter '*.dll').Count -ne 0) {
    throw 'The OpenSSL prerequisite must contain no shared libraries.'
}
python .github/scripts/inspect_pe.py --expect 0xAA64 $tool
if ($LASTEXITCODE -ne 0) { throw 'OpenSSL tool is not an ARM64 PE.' }
$actual = & $tool version -a
if ($LASTEXITCODE -ne 0 -or $actual[0] -notmatch '^OpenSSL 4\.0\.3\b') {
    throw 'Unexpected effective OpenSSL tool version.'
}
$actual | Set-Content -LiteralPath (Join-Path $evidence 'openssl-version.txt')
foreach ($name in @('libcrypto', 'libssl')) {
    $headers = & dumpbin /headers (Join-Path $lib "$name.lib")
    if ($LASTEXITCODE -ne 0 -or -not ($headers -match 'AA64 machine') -or
        ($headers -match '(8664|14C) machine')) { throw "$name must contain ARM64 objects only." }
    $headers | Set-Content -LiteralPath (Join-Path $evidence "$name-headers.txt")
    $directives = & dumpbin /directives (Join-Path $lib "$name.lib")
    if ($LASTEXITCODE -ne 0 -or ($directives -match 'LIBCMT|MT_StaticRelease')) {
        throw "$name must not select the static MSVC CRT."
    }
    $directives | Set-Content -LiteralPath (Join-Path $evidence "$name-directives.txt")
}
Copy-Item -LiteralPath (Join-Path $source 'LICENSE.txt') -Destination $evidence
@{
    version = $version; source_url = $url; source_sha256 = $sha256
    source_sha256_url = "$url.sha256"; target = $target
    linkage = 'static'; crt = 'dynamic'; compiler = $compiler; assembler = $clang
    configure = $configure; source_sha = $env:GITHUB_SHA; run_id = $env:GITHUB_RUN_ID
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'source-provenance.json')

@(
    "OPENSSL_DIR=$prefix", "OPENSSL_INCLUDE_DIR=$(Join-Path $prefix 'include')", "OPENSSL_LIB_DIR=$lib",
    'OPENSSL_STATIC=1', 'OPENSSL_NO_VENDOR=1', 'PIP_NO_BINARY=cryptography', 'PIP_NO_CACHE_DIR=1',
    "CRYPTOGRAPHY_OPENSSL_EVIDENCE=$evidence"
    "CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER=$linker"
) | Add-Content -LiteralPath $env:GITHUB_ENV
# Subsequent steps need the same native MSVC environment for the source wheel.
foreach ($name in @('PATH', 'INCLUDE', 'LIB', 'LIBPATH', 'VSINSTALLDIR', 'VCINSTALLDIR',
    'VCToolsInstallDir', 'WindowsSdkDir', 'WindowsSDKVersion', 'VSCMD_ARG_HOST_ARCH', 'VSCMD_ARG_TGT_ARCH')) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { "$name=$value" | Add-Content -LiteralPath $env:GITHUB_ENV }
}
Write-Host "Native ARM64 static OpenSSL $version / dynamic CRT prerequisite verified."
