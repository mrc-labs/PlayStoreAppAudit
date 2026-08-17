param(
    [Parameter(Mandatory = $false)]
    [string]$PythonExe = "python",

    [Parameter(Mandatory = $false)]
    [string]$RepoRoot = (Get-Location).Path,

    [Parameter(Mandatory = $false)]
    [string]$OutputRoot = "artifact\windows-x64-local",

    [Parameter(Mandatory = $false)]
    [string]$ExpectedPeMachine = "0x8664",

    [Parameter(Mandatory = $false)]
    [string]$ExpectedPlatformMachine = "AMD64",

    [Parameter(Mandatory = $false)]
    [string]$PackageArch = "x64",

    [Parameter(Mandatory = $false)]
    [switch]$UseMSVC,

    [Parameter(Mandatory = $false)]
    [switch]$PrivateBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Fail([string]$Message) {
    throw $Message
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Set-Location -LiteralPath $RepoRoot

if ([IO.Path]::IsPathRooted($PythonExe)) {
    $Python = $PythonExe
} else {
    $Python = (Get-Command $PythonExe -ErrorAction Stop).Source
}

if ([IO.Path]::IsPathRooted($OutputRoot)) {
    $BuildRoot = $OutputRoot
} else {
    $BuildRoot = Join-Path $RepoRoot $OutputRoot
}

$InspectPe = Join-Path $RepoRoot ".github\scripts\inspect_pe.py"
$ValidateStandalone = Join-Path $RepoRoot ".github\scripts\validate_windows_standalone.py"

if (-not (Test-Path -LiteralPath $Python)) {
    Fail "Python executable was not found: $Python"
}
if (-not (Test-Path -LiteralPath $InspectPe)) {
    Fail "PE inspection helper was not found: $InspectPe"
}
if (-not (Test-Path -LiteralPath $ValidateStandalone)) {
    Fail "Standalone validation helper was not found: $ValidateStandalone"
}

Write-Host "=== WINDOWS STANDALONE BUILD ==="
Write-Host "Repository: $RepoRoot"
Write-Host "Python:     $Python"
Write-Host "Output:     $BuildRoot"
$CompilerLabel = if ($UseMSVC) { "MSVC latest" } else { "Nuitka default/available compiler" }

Write-Host "Arch:       $PackageArch"
Write-Host "Machine:    $ExpectedPlatformMachine"
Write-Host "Compiler:   $CompilerLabel"
Write-Host ""

$ReportedMachine = (& $Python -c "import platform; print(platform.machine().upper())").Trim()
if ($LASTEXITCODE -ne 0) {
    Fail "Could not read platform.machine() from the selected Python."
}

& $Python -c "import struct, sys; print(sys.version); print(struct.calcsize('P') * 8); assert sys.version_info[:2] == (3, 13); assert struct.calcsize('P') * 8 == 64"
if ($LASTEXITCODE -ne 0) {
    Fail "Windows packaging requires standard 64-bit Python 3.13."
}

$ExpectedMachineNormalized = $ExpectedPlatformMachine.ToUpperInvariant()
$ReportedMachineNormalized = $ReportedMachine.ToUpperInvariant()
$MachineMatches = $ReportedMachineNormalized -eq $ExpectedMachineNormalized

if ($ExpectedMachineNormalized -eq "AMD64" -and $ReportedMachineNormalized -eq "X86_64") {
    $MachineMatches = $true
}

if (-not $MachineMatches) {
    Fail "Expected native $ExpectedPlatformMachine Python, but platform.machine() reported $ReportedMachine."
}

Write-Host "Reported machine: $ReportedMachine"

& $Python -c "import PySide6; print('PySide6', PySide6.__version__); assert tuple(map(int, PySide6.__version__.split('.')[:2])) >= (6, 11)"
if ($LASTEXITCODE -ne 0) {
    Fail "PySide6 6.11+ verification failed."
}

& $Python -m nuitka --version
if ($LASTEXITCODE -ne 0) {
    Fail "Nuitka is not available in the selected Python environment."
}

$AppVersion = (& $Python -c "from playstore_app_audit import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $AppVersion) {
    Fail "Could not read the canonical application version."
}
if ($AppVersion -notmatch '^\d+\.\d+\.\d+$') {
    Fail "Unexpected application version: $AppVersion"
}

& $Python -c "import pathlib, tomllib; from playstore_app_audit import __version__; metadata=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version']; assert __version__ == metadata"
if ($LASTEXITCODE -ne 0) {
    Fail "Package version and pyproject.toml version do not match."
}

$NuitkaOutput = Join-Path $BuildRoot "nuitka"
$PackageName = "PlayStoreAppAudit-v$AppVersion-windows-$PackageArch"
$PackageDir = Join-Path $BuildRoot $PackageName
$ZipPath = Join-Path $BuildRoot "$PackageName.zip"
$ChecksumPath = "$ZipPath.sha256"
$IconPath = Join-Path $BuildRoot "app_icon.ico"

if (Test-Path -LiteralPath $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $NuitkaOutput | Out-Null

Write-Host ""
Write-Host "=== GENERATE WINDOWS ICON ==="
& $Python -c "from app_icon import generate_windows_ico; print(generate_windows_ico(r'$($BuildRoot.Replace('\','\\'))'))"
if ($LASTEXITCODE -ne 0) {
    Fail "Icon generation failed."
}
if (-not (Test-Path -LiteralPath $IconPath)) {
    Fail "Expected icon was not generated: $IconPath"
}

Write-Host ""
Write-Host "=== BUILD NUITKA STANDALONE DIRECTORY ==="

$NuitkaArgs = @(
    "-m", "nuitka",
    "--mode=standalone",
    "--enable-plugin=pyside6",
    "--noinclude-qt-plugins=platforminputcontexts",
    "--noinclude-qt-translations",
    "--windows-console-mode=disable",
    "--nofollow-import-to=PIL",
    "--assume-yes-for-downloads",
    "--windows-icon-from-ico=$IconPath",
    "--file-version=$AppVersion",
    "--product-version=$AppVersion",
    "--product-name=PlayStoreAppAudit",
    "--file-description=PlayStoreAppAudit",
    "--output-filename=PlayStoreAppAudit.exe",
    "--output-dir=$NuitkaOutput"
)

if ($UseMSVC) {
    $NuitkaArgs += "--msvc=latest"
}

$NuitkaArgs += "main.py"

& $Python @NuitkaArgs
if ($LASTEXITCODE -ne 0) {
    Fail "Nuitka standalone build failed."
}

$DistDir = Get-ChildItem -LiteralPath $NuitkaOutput -Directory |
    Where-Object { $_.Name -like "*.dist" } |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1

if (-not $DistDir) {
    Fail "Nuitka did not create a .dist directory."
}

Write-Host ""
Write-Host "Raw standalone directory: $($DistDir.FullName)"

# qpdf.dll is not required by Play Store App Audit.
$QPdfFiles = @(
    Get-ChildItem -LiteralPath $DistDir.FullName -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ieq "qpdf.dll" }
)
foreach ($File in $QPdfFiles) {
    Write-Host "Removing unused Qt PDF image plugin: $($File.FullName)"
    Remove-Item -LiteralPath $File.FullName -Force
}

Write-Host ""
Write-Host "=== VALIDATE STANDALONE CONTENTS ==="
& $Python $ValidateStandalone $DistDir.FullName
if ($LASTEXITCODE -ne 0) {
    Fail "Standalone runtime validation failed."
}

$Exe = Get-ChildItem -LiteralPath $DistDir.FullName -Recurse -File -Filter "PlayStoreAppAudit.exe" |
    Select-Object -First 1
if (-not $Exe) {
    Fail "PlayStoreAppAudit.exe was not found in the standalone directory."
}

Write-Host ""
Write-Host "=== VALIDATE PRIMARY EXE ==="
$PeArchitecture = & $Python $InspectPe --expect $ExpectedPeMachine $Exe.FullName
if ($LASTEXITCODE -ne 0) {
    Fail "Primary executable PE architecture validation failed."
}
Write-Host "PE architecture: $PeArchitecture"

$ExpectedWindowsVersion = "$AppVersion.0"
$VersionInfo = (Get-Item -LiteralPath $Exe.FullName).VersionInfo
if ($VersionInfo.FileVersion -ne $ExpectedWindowsVersion) {
    Fail "Expected FileVersion $ExpectedWindowsVersion, found $($VersionInfo.FileVersion)."
}
if ($VersionInfo.ProductVersion -ne $ExpectedWindowsVersion) {
    Fail "Expected ProductVersion $ExpectedWindowsVersion, found $($VersionInfo.ProductVersion)."
}
Write-Host "FileVersion:    $($VersionInfo.FileVersion)"
Write-Host "ProductVersion: $($VersionInfo.ProductVersion)"

Write-Host ""
Write-Host "=== PACKAGED SMOKE TEST ==="
$OldQtPlatform = $env:QT_QPA_PLATFORM
$OldSmoke = $env:PLAYSTORE_APP_AUDIT_SMOKE_TEST
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:PLAYSTORE_APP_AUDIT_SMOKE_TEST = "1"

    $Process = Start-Process `
        -FilePath $Exe.FullName `
        -WorkingDirectory $DistDir.FullName `
        -PassThru `
        -WindowStyle Hidden

    if (-not $Process.WaitForExit(60000)) {
        $Process.Kill()
        $Process.WaitForExit()
        Fail "Packaged application did not finish its deterministic smoke test within 60 seconds."
    }
    if ($Process.ExitCode -ne 0) {
        Fail "Packaged application smoke test failed with exit code $($Process.ExitCode)."
    }
}
finally {
    $env:QT_QPA_PLATFORM = $OldQtPlatform
    $env:PLAYSTORE_APP_AUDIT_SMOKE_TEST = $OldSmoke
}
Write-Host "Packaged smoke test: PASS"

Write-Host ""
Write-Host "=== CREATE VERSIONED PACKAGE ==="
Copy-Item -LiteralPath $DistDir.FullName -Destination $PackageDir -Recurse

if ($PrivateBuild) {
    @(
        "PRIVATE TECHNICAL TEST BUILD"
        "NOT FOR PUBLIC DISTRIBUTION"
        ""
        "Application version: $AppVersion"
        "Packaging: Nuitka standalone"
        "Purpose: local runtime/layout validation"
        "Remaining public-release work includes final original icon and legal/compliance materials."
    ) | Set-Content -LiteralPath (Join-Path $PackageDir "PRIVATE-TEST-BUILD.txt") -Encoding utf8
}

$PythonVersion = (& $Python -c "import sys; print(sys.version.replace(chr(10), chr(32)))").Trim()
if ($LASTEXITCODE -ne 0) {
    Fail "Could not record the Python version."
}

$PySideVersion = (& $Python -c "import PySide6; print(PySide6.__version__)").Trim()
if ($LASTEXITCODE -ne 0) {
    Fail "Could not record the PySide6 version."
}

$NuitkaVersion = (& $Python -c "from importlib.metadata import version; print(version('Nuitka'))").Trim()
if ($LASTEXITCODE -ne 0) {
    Fail "Could not record the Nuitka version."
}

$BuildInfoLines = @(
    "Application version: $AppVersion"
    "Windows file version: $($VersionInfo.FileVersion)"
    "Windows product version: $($VersionInfo.ProductVersion)"
    "Package architecture: $PackageArch"
    "Expected platform machine: $ExpectedPlatformMachine"
    "Reported platform machine: $ReportedMachine"
    "PE executable architecture: $PeArchitecture"
    "Python: $PythonVersion"
    "PySide6: $PySideVersion"
    "Nuitka: $NuitkaVersion"
    "Packaging: standalone"
)

if ($env:GITHUB_ACTIONS -eq "true") {
    $BuildInfoLines += @(
        "GitHub repository: $env:GITHUB_REPOSITORY"
        "GitHub SHA: $env:GITHUB_SHA"
        "GitHub ref: $env:GITHUB_REF"
        "GitHub ref name: $env:GITHUB_REF_NAME"
        "GitHub event: $env:GITHUB_EVENT_NAME"
        "GitHub workflow: $env:GITHUB_WORKFLOW"
        "GitHub run ID: $env:GITHUB_RUN_ID"
        "GitHub run attempt: $env:GITHUB_RUN_ATTEMPT"
        "Runner OS: $env:RUNNER_OS"
        "Runner architecture: $env:RUNNER_ARCH"
        "Runner image OS: $env:ImageOS"
        "Runner image version: $env:ImageVersion"
        "Python platform tag: $env:PYTHON_PLATFORM_TAG"
        "Python PE architecture: $env:PYTHON_PE_ARCHITECTURE"
        "PySide6-Essentials wheel tag: $env:PYSIDE6_WHEEL_TAG"
        "PySide6 QtCore PE architecture: $env:PYSIDE6_QTCORE_PE_ARCHITECTURE"
        "Managed ADB path: $env:MANAGED_ADB_PATH"
        "Managed ADB version: $env:MANAGED_ADB_VERSION"
        "Managed ADB PE architecture: $env:MANAGED_ADB_PE_ARCHITECTURE"
        "Managed ADB execution validation: $env:MANAGED_ADB_EXECUTION"
        "Signing: unsigned CI artifact"
    )
} else {
    $BuildInfoLines += "Signing: unsigned local artifact"
}

$BuildInfoLines |
    Set-Content -LiteralPath (Join-Path $PackageDir "BUILD-INFO.txt") -Encoding utf8

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $PackageDir -DestinationPath $ZipPath -CompressionLevel Optimal

$ZipHash = (& $Python -c "import hashlib, sys; print(hashlib.file_digest(open(sys.argv[1], 'rb'), 'sha256').hexdigest())" $ZipPath).Trim()
if ($LASTEXITCODE -ne 0 -or -not $ZipHash) {
    Fail "Could not calculate the ZIP SHA-256."
}

"$ZipHash  $([IO.Path]::GetFileName($ZipPath))" |
    Set-Content -LiteralPath $ChecksumPath -Encoding ascii

Write-Host ""
Write-Host "=== FINAL PACKAGE VALIDATION ==="
& $Python $ValidateStandalone $PackageDir
if ($LASTEXITCODE -ne 0) {
    Fail "Final versioned package validation failed."
}

Write-Host ""
Write-Host "=== QT RUNTIME INVENTORY ==="
Get-ChildItem -LiteralPath $PackageDir -Recurse -File |
    Where-Object { $_.Name -like "Qt6*.dll" } |
    Sort-Object Name |
    Select-Object -ExpandProperty Name -Unique

Write-Host ""
Write-Host "=== RESULT ==="
Write-Host "Package directory: $PackageDir"
Write-Host "Executable:        $(Join-Path $PackageDir 'PlayStoreAppAudit.exe')"
Write-Host "ZIP:               $ZipPath"
Write-Host "ZIP SHA-256:       $ZipHash"
Write-Host "Checksum:          $ChecksumPath"
