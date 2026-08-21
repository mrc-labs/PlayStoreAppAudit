[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Invoke-GitText {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $output = & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed:`n$($output -join [Environment]::NewLine)"
    }
    return ($output -join [Environment]::NewLine).TrimEnd()
}

$repoRoot = (Invoke-GitText @('rev-parse', '--show-toplevel')).Trim()
Set-Location $repoRoot

$status = Invoke-GitText @('status', '--short')
if ($status) {
    throw "Working tree is dirty. Stop and review it before exporting a chat handoff:`n$status"
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$handoffName = "PlayStoreAppAudit-v1.6-chat-handoff-$timestamp"
$outputDir = Join-Path ([System.IO.Path]::GetTempPath()) $handoffName
$zipPath = "$outputDir.zip"

if (Test-Path -LiteralPath $outputDir) {
    Remove-Item -LiteralPath $outputDir -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
New-Item -ItemType Directory -Path $outputDir | Out-Null

$files = @(
    'docs/HANDOFF_V1.6.md',
    'docs/ROADMAP.md',
    'docs/PROJECT_STATUS.md',
    'docs/PROJECT_DECISIONS.md',
    'AGENTS.md',
    'docs/BUILDING.md',
    'docs/RELEASE_NOTES.md',
    'CHANGELOG.md',
    'README.md',
    'pyproject.toml',
    'requirements.txt',
    'requirements-dev.txt'
)

foreach ($relativePath in $files) {
    $source = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required handoff file is missing: $relativePath"
    }

    $destination = Join-Path $outputDir $relativePath
    $destinationParent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationParent)) {
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $destination
}

$branch = Invoke-GitText @('branch', '--show-current')
$head = Invoke-GitText @('rev-parse', 'HEAD')
$remote = Invoke-GitText @('remote', 'get-url', 'origin')
$recentCommits = Invoke-GitText @('log', '-15', '--date=iso-strict', '--pretty=format:%h %ad %d %s')
$recentTags = Invoke-GitText @('tag', '--sort=-creatordate')
$trackedFiles = Invoke-GitText @('ls-files', 'playstore_app_audit', 'tests', '.github/workflows', '.github/scripts')

$pythonVersion = ''
try {
    $pythonVersion = (& python --version 2>&1 | Out-String).Trim()
} catch {
    $pythonVersion = "python command unavailable: $($_.Exception.Message)"
}

$py313Version = ''
try {
    $py313Version = (& py -3.13 --version 2>&1 | Out-String).Trim()
} catch {
    $py313Version = "py -3.13 unavailable: $($_.Exception.Message)"
}

$ghSection = @()
if (Get-Command gh -ErrorAction SilentlyContinue) {
    try {
        $releaseJson = (& gh release view --json tagName,name,isDraft,isPrerelease,publishedAt,url 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $releaseJson) {
            $ghSection += "## GitHub latest release via gh"
            $ghSection += ''
            $ghSection += '```json'
            $ghSection += $releaseJson
            $ghSection += '```'
            $ghSection += ''
        }
    } catch {
        $ghSection += "GitHub release lookup failed: $($_.Exception.Message)"
        $ghSection += ''
    }

    try {
        $prsJson = (& gh pr list --state merged --limit 15 --json number,title,mergedAt,mergeCommit,url 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $prsJson) {
            $ghSection += "## Recent merged PRs via gh"
            $ghSection += ''
            $ghSection += '```json'
            $ghSection += $prsJson
            $ghSection += '```'
            $ghSection += ''
        }
    } catch {
        $ghSection += "GitHub PR lookup failed: $($_.Exception.Message)"
        $ghSection += ''
    }
} else {
    $ghSection += '## GitHub CLI metadata'
    $ghSection += ''
    $ghSection += '`gh` was not available. The new chat should verify release/PR state through connected GitHub.'
    $ghSection += ''
}

$snapshot = @(
    '# Play Store App Audit Repository Snapshot',
    '',
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
    '',
    '## Repository identity',
    '',
    "- Root: `$repoRoot`",
    "- Origin: `$remote`",
    "- Branch: `$branch`",
    "- HEAD: `$head`",
    '- Working tree: clean',
    "- Python: `$pythonVersion`",
    "- Python 3.13 launcher: `$py313Version`",
    '',
    '## Recent commits',
    '',
    '```text',
    $recentCommits,
    '```',
    '',
    '## Recent tags',
    '',
    '```text',
    (($recentTags -split "`r?`n" | Select-Object -First 15) -join [Environment]::NewLine),
    '```',
    '',
    '## Tracked source, test and workflow files',
    '',
    '```text',
    $trackedFiles,
    '```',
    ''
)

$snapshot += $ghSection

$snapshotPath = Join-Path $outputDir 'REPOSITORY_SNAPSHOT.md'
$snapshot -join [Environment]::NewLine | Set-Content -LiteralPath $snapshotPath -Encoding utf8

Compress-Archive -Path (Join-Path $outputDir '*') -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ''
Write-Host 'Chat handoff export completed successfully.'
Write-Host "Folder: $outputDir"
Write-Host "ZIP:    $zipPath"
Write-Host ''
Write-Host 'Attach the ZIP to the new development chat.'
