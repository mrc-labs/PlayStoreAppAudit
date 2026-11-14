using namespace System.Security.Cryptography
using namespace System.Security.Cryptography.X509Certificates
param([Parameter(Mandatory = $true)][string]$InputsPath,
      [Parameter(Mandatory = $true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Supported Windows X509Chain/CryptoAPI; ExtraStore supplies untrusted chain
# material in memory. No CustomRootTrust, store writes or verification bypass.
if (-not $IsWindows -or [Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -ne 'X64') {
    throw 'Native Windows x64 required.'
}
if ($PSVersionTable.PSVersion.PreReleaseLabel -or [Runtime.InteropServices.RuntimeInformation]::FrameworkDescription -match 'preview|rc\.') {
    throw 'Stable host PowerShell/.NET required.'
}
$headSha = (git rev-parse HEAD).Trim()
if ($headSha -ne $env:EXPECTED_SHA -or $headSha -ne $env:GITHUB_SHA) { throw 'Exact execution SHA mismatch.' }
$spec = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'provider_ca_security_sources.json') -Raw | ConvertFrom-Json
foreach ($item in $spec.sources) {
    $hash = (Get-FileHash -LiteralPath (Join-Path $InputsPath $item.name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $item.sha256) { throw "Changed original native-chain input: $($item.name)" }
}
function Hash-Bytes([byte[]]$Data) { [Convert]::ToHexString([SHA256]::HashData($Data)).ToLowerInvariant() }
function New-SystemChain {
    $chain = [X509Chain]::new()
    $chain.ChainPolicy.TrustMode = [X509ChainTrustMode]::System
    $chain.ChainPolicy.VerificationFlags = [X509VerificationFlags]::NoFlag
    $chain.ChainPolicy.RevocationMode = [X509RevocationMode]::Online
    $chain.ChainPolicy.RevocationFlag = [X509RevocationFlag]::ExcludeRoot
    $chain.ChainPolicy.UrlRetrievalTimeout = [TimeSpan]::FromSeconds(10)
    [void]$chain.ChainPolicy.ApplicationPolicy.Add([Oid]::new('1.3.6.1.5.5.7.3.1'))
    return $chain
}
$metadata = Get-Content -LiteralPath (Join-Path $InputsPath 'impacted-intermediates.json') -Raw | ConvertFrom-Json
$badKeys = @($metadata | ForEach-Object { $_.spki_sha256.ToLowerInvariant() } | Sort-Object -Unique)
if ($badKeys.Count -ne 8) { throw 'Expected eight reviewed compromised keys.' }
$tcp = [Net.Sockets.TcpClient]::new()
$stream = $null
try {
    if (-not $tcp.ConnectAsync('www.python.org', 443).Wait(20000)) { throw 'Default-trust positive TCP timeout.' }
    $stream = [Net.Security.SslStream]::new($tcp.GetStream(), $false)
    $stream.ReadTimeout = 20000
    $stream.WriteTimeout = 20000
    $options = [Net.Security.SslClientAuthenticationOptions]::new()
    $options.TargetHost = 'www.python.org'
    $options.CertificateRevocationCheckMode = [X509RevocationMode]::Online
    $stream.AuthenticateAsClient($options)
    $leaf = [X509CertificateLoader]::LoadCertificate($stream.RemoteCertificate.Export([X509ContentType]::Cert))
    $positiveChain = New-SystemChain
    try {
        $positiveAccepted = $positiveChain.Build($leaf)
        if (-not $positiveAccepted -or -not $leaf.MatchesHostname('www.python.org', $false, $false)) {
            throw "Native chain positive failed: $($positiveChain.ChainStatus.Status -join ',')"
        }
        $positive = @{host='www.python.org'; authenticated=$stream.IsAuthenticated; encrypted=$stream.IsEncrypted
            protocol=$stream.SslProtocol.ToString(); chain_accepted=$positiveAccepted; peer_sha256=(Hash-Bytes $leaf.RawData)
            trust_mode='System'; revocation='Online'; verification_flags='NoFlag'; scope='Ordinary defaults, no explicit CA or validation callback'}
    } finally { $positiveChain.Dispose(); $leaf.Dispose() }
} finally { if ($stream) { $stream.Dispose() }; $tcp.Dispose() }
$cases = @()
$files = @(Get-ChildItem -LiteralPath (Join-Path $InputsPath 'chains/chains/rollover') -Filter '*.pem' -File)
if ($files.Count -ne 2) { throw 'Exactly two original rollover PEM cases required.' }
foreach ($file in $files) {
    $certs = [X509Certificate2Collection]::new()
    $certs.ImportFromPem([IO.File]::ReadAllText($file.FullName))
    if ($certs.Count -lt 3) { throw 'Rollover chain truncated.' }
    $hostname = $certs[0].GetNameInfo([X509NameType]::DnsName, $false)
    if (-not $certs[0].MatchesHostname($hostname, $false, $false)) { throw 'Rollover SAN/hostname input invalid.' }
    foreach ($cert in $certs) {
        if ($cert.NotBefore.ToUniversalTime() -gt [DateTime]::UtcNow -or $cert.NotAfter.ToUniversalTime() -le [DateTime]::UtcNow) {
            throw 'Rollover fixture validity expired; not a trust-policy rejection.'
        }
    }
    $chain = New-SystemChain
    try {
        for ($i = 1; $i -lt $certs.Count; $i++) { [void]$chain.ChainPolicy.ExtraStore.Add($certs[$i]) }
        $accepted = $chain.Build($certs[0])
        $elements = @($chain.ChainElements | ForEach-Object {
            @{sha256=(Hash-Bytes $_.Certificate.RawData); spki_sha256=(Hash-Bytes $_.Certificate.PublicKey.ExportSubjectPublicKeyInfo())
              status=@($_.ChainElementStatus | ForEach-Object { $_.Status.ToString() })}
        })
        $compromised = @($elements | Where-Object { $_.spki_sha256 -in $badKeys })
        $specificallyDistrusted = @($compromised | Where-Object { ($_.status -join ',') -match 'ExplicitDistrust|Revoked' })
        $status = @($chain.ChainStatus | ForEach-Object { $_.Status.ToString() })
        $trustFailure = @($status | Where-Object { $_ -match 'ExplicitDistrust|Revoked|UntrustedRoot|PartialChain' }).Count -gt 0
        $cases += @{fixture=$file.Name; hostname=$hostname; leaf_sha256=(Hash-Bytes $certs[0].RawData)
            accepted=$accepted; hostname_matches=$true; validity_checked=$true; status=$status; elements=$elements
            compromised_native_elements=$compromised.Count; custom_trust_count=$chain.ChainPolicy.CustomTrustStore.Count
            trust_mode=$chain.ChainPolicy.TrustMode.ToString(); verification_flags=$chain.ChainPolicy.VerificationFlags.ToString()
            revocation=$chain.ChainPolicy.RevocationMode.ToString(); specifically_distrusted_compromised_elements=$specificallyDistrusted.Count
            result=$(if (-not $accepted -and $trustFailure -and $compromised.Count -gt 0) { 'PASS native trust rejection/path; Qt guard mapping required' } else { 'BLOCKED native chain gate' })}
    } finally { $chain.Dispose(); foreach ($cert in $certs) { $cert.Dispose() } }
}
$report = @{execution_sha=$headSha; provider='Windows native X509Chain/CryptoAPI via existing PowerShell host'
    powershell=$PSVersionTable.PSVersion.ToString(); runtime=[Runtime.InteropServices.RuntimeInformation]::FrameworkDescription
    os=[Environment]::OSVersion.VersionString; architecture='X64'; trust_mode='System'; revocation='Online'; verification_flags='NoFlag'
    positive=$positive; rollover=$cases; scope='Native chain-engine verification of offline PEMs; distinct from Qt manual API and a rollover TLS handshake'
    result=$(if (@($cases | Where-Object { $_.result -ne 'PASS native trust rejection/path; Qt guard mapping required' }).Count -eq 0) { 'PASS native paths; separate Qt ancestor policy check required' } else { 'BLOCKED native rollover chain engine' })}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "Native rollover chain engine: $($report.result)"
if ($report.result -notlike 'PASS*') { throw 'Native rollover chain gate not satisfied; see retained per-case JSON.' }
