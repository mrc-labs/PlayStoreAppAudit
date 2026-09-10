# Local APK parser foundation

Last updated: 2026-09-10

## Decision

The v2.0 parser foundation uses Python's standard-library `zipfile` boundary plus
`pyaxmlparser==0.3.31` for Android binary XML (`AndroidManifest.xml`) and resource-table
decoding. Production code lives in `playstore_app_audit.services.local_apk`; the
immutable result and typed failure models live in
`playstore_app_audit.domain.local_artifacts`. Neither layer depends on Qt.

The parser accepts one existing regular file with a case-insensitive `.apk`
suffix. It returns `LocalArtifactParseResult`, containing exactly one
`LocalArtifact` or `LocalArtifactParseFailure`. Missing values stay `None`; they
are not replaced with Android defaults or guessed from file names.

## Approaches considered

- Android SDK `aapt2`/`apkanalyzer` is authoritative but would add a large,
  separately managed cross-platform toolchain to a metadata feature. It is not
  an acceptable required runtime dependency for the desktop parser.
- Android SDK `apksigner` is the preferred reference tool if cryptographic APK
  signature verification becomes a justified product requirement. It is not a
  general manifest/resource parser and is not bundled for this foundation.
- Full `androguard` 4.1.4 is actively maintained and capable, but its reverse-
  engineering scope and dependency graph (including analysis, database, graph,
  plotting, interactive and instrumentation packages) are disproportionate.
- `apkparser-ag` 0.0.2 is the newer Androguard archive split, but it is still a
  young beta and currently brings DEX, signature, terminal-formatting,
  `python-magic`, ASN.1 and cryptographic dependencies not needed here.
- `axml` 0.0.2 is a recent, small Apache-2.0 extraction of Androguard's AXML/ARSC
  code and declares Python 3.13 support. It was rejected after source/runtime
  inspection showed that importing its parser configures the process-wide root
  logger with a Rich handler; a parsing dependency must not silently change the
  desktop application's logging behavior.
- `apkutils` 2.0.5 is maintained, but includes DEX/ELF/signature and CLI scope
  plus a broader dependency set. The public GitHub repository is described as a
  mirror of its primary Gitee project.
- A new project-owned binary-AXML parser would avoid a dependency but would make
  this application responsible for a complex, security-sensitive file format.

`pyaxmlparser` is a focused, established Apache-2.0 implementation whose direct
AXML and ARSC modules accept bytes without taking ownership of archive I/O. Its
latest stable release for this same project remains 0.3.31 (published March 20,
2024) and its declared Python classifiers are stale, so the version is pinned
and the project does not use its higher-level APK or signature API. Direct
imports leave root logging unchanged. Source checks passed on Windows x64 with
Python 3.13.15 and 3.14.6.

## Supported metadata and identity

For a valid standalone APK, the immutable `LocalArtifact` currently carries:

- `artifact_format` (`apk`);
- SHA-256 of the exact file bytes as `artifact_sha256`/`artifact_id`;
- exact manifest package ID and a separate `package_lookup_key`;
- application label when literal or resolvable from the default resource
  configuration, plus the original resource reference when present;
- `versionName` when literal or safely resolvable, plus its original resource
  reference when present;
- `versionCode`, `versionCodeMajor`, and a derived `long_version_code` when both
  numeric components permit it;
- declared min, target and compile SDK values without invented defaults;
- declared application debuggable state when it is explicitly recognizable;
- sorted, deduplicated manifest permission and feature names;
- the manifest icon resource/path reference (metadata only; no extraction);
- file name, resolved absolute/canonical `Path`, byte size and UTC modified time;
- typed warnings for optional label/version-name resource values that could not
  be resolved.

Two APKs with the same package ID remain separate artifacts when their bytes,
and therefore SHA-256 values, differ. Package identity is only the future Store
lookup key; it never replaces artifact identity.

## Untrusted-input boundary

The service captures the input and its SHA-256 in one bounded streaming pass.
The snapshot keeps at most 8 MiB in memory and spills larger APKs to a private,
automatically removed temporary file; it never loads an arbitrarily large APK
into memory. ZIP and metadata parsing operate only on those captured bytes, then
the original file is re-hashed before success. This prevents a rewrite between
hashing and parsing from associating metadata with a different SHA-256,
including same-size changes whose filesystem timestamp was restored.

Before `zipfile` allocates the snapshot's central directory, the service reads
and checks a bounded ZIP end record. Defaults reject files over 2 GiB,
ZIP64/multi-disk archives, central directories over 64 MiB, more than 50,000
entries and declared total expansion over 8 GiB. Only the exact manifest and,
when required, `resources.arsc` are decompressed. Streaming reads cap them at 4
MiB and 64 MiB respectively, cap their compression ratio at 1,000:1, reject
encryption, verify the resulting size/CRC through `zipfile`, and never extract
an archive path to disk.

Duplicate manifest/resource-table names, missing manifests, inconsistent ZIP
offsets, truncated archives, invalid package IDs, invalid binary manifests and
detected split or split-dependent APKs produce stable typed failures. The source
remains open while the captured snapshot is parsed; source size and nanosecond
modified time are checked again before success in addition to the final content
hash.

These limits bound memory and decompression work but do not provide a separate
process, CPU deadline or parser sandbox. A hostile binary manifest within the
size limit can still consume parser CPU. No parser can guarantee that the source
path remains unchanged after a successful return; process isolation can be
reconsidered only with measured evidence and a packaging-safe design.

## Signing status

This foundation performs neither certificate extraction nor cryptographic APK
signature verification. SHA-256 identifies bytes; it does not authenticate a
publisher or prove Android installability.

Partial ZIP inspection would cover only v1/JAR material and could miss or
misrepresent v2/v3 signing blocks; v4 also uses a separate `.idsig` file. Proper
verification must apply Android's scheme selection, signer, digest, lineage and
platform-version rules. If later product requirements justify it, evaluate the
official Android `apksigner verify --print-certs`/`apksig` implementation behind
a separate explicit boundary rather than labeling certificate extraction as
verification.

## Unsupported formats

- Individual APKs detected as split/configuration APKs, or bases declaring
  required split types, fail as `unsupported_split`; split installation
  semantics are not inferred.
- APK sets (`.apks`) are not opened or expanded.
- Android App Bundles (`.aab`) are not supported; their bundle manifest/resource
  model is different from a standalone installable APK.
- Other ZIP-like files and renamed unsupported formats are not claimed as APKs;
  a `.apk` must still pass the archive and binary-manifest checks.

## Dependency, legal and packaging effect

`pyaxmlparser==0.3.31`, still the same project's latest stable PyPI release at
the 2026-09-10 closure review, is added as one direct Apache-2.0 runtime
dependency. Its current dependency metadata adds `lxml`, `click>=6.7` and
`asn1crypto>=0.24.0`.
The service directly imports only the AXML/ARSC modules; it does not use the
dependency's CLI or combined APK/signature surface. Current resolved wheels
include license/notice files. `lxml` contains compiled native components; the
other three distributions are pure Python. `pip check` passes on Python 3.13
and 3.14.

The project's fail-closed Nuitka evidence logic will inventory only packages
actually compiled or copied into a final standalone runtime. Apache/BSD/MIT
dependencies add applicable package notices but do not add a corresponding-
source obligation like the Qt/LGPL source set. The consolidated source-bundle
mechanism and release asset count therefore do not change. No Nuitka build was
run for this source-only foundation; actual standalone inclusion and legal
inventory remain a later Windows x64 packaging gate before v2.0 release freeze.

## Next phase

The service-level package-deduplicated Store/provider fan-out is now complete at
the source boundary. It groups `LocalArtifact` objects by exact
`package_lookup_key` within one homogeneous lookup context, reuses the existing
Store/cache/provider services, and shares package evidence without collapsing
artifact SHA-256 identities. The Local APK source selects standalone files or
discovers a folder without parsing, then invokes this parser outside the GUI
thread only when Run is pressed, preserves partial successes, and keeps source
state session-only. The persistent Library phase 5a core is complete. It
reuses this parser for explicit recursive directory scans and persists versioned
SHA-256 artifact and location state without Store/provider evidence. The
separate Library UI is no longer exposed in v2.0; the core remains future
infrastructure. See `LOCAL_APK_LIBRARY.md`.
