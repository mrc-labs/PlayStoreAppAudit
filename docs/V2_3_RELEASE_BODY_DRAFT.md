# Store App Audit v2.3.0 release-body draft

**DRAFT, unpublished.** Phase B prepares source and release wording. Final six-platform build acceptance, assembly and public verification remain pending in Phase C/D. Remove this draft notice only when the recorded evidence supports publication.

## What's New / Highlights

### Added

- **Play Store Category** in results, Details, custom views, Smart Queries and CSV/HTML/JSON exports.
- Up to **3 named Custom Views per source family**, independently for Phone / App List and Local APK, with create/select/update/rename/delete and restart persistence.
- **Review Duplicates…** for Local APK sources: explicit keeper-safe cleanup of identical SHA-256 bytes at distinct physical paths. Same Version Variant and Multiple Versions are informational and never automatically deleted.

### Changed

- Local APK Mass Rename `{category}` uses the real Store category.
- Existing v2.2 Custom layouts migrate conservatively into named views.
- Legacy installer-classification Smart Queries retain their meaning after duplicated saved installer-category state is retired.

## Compatibility and distribution

Intended packages: Windows x64 and ARM64, Linux x64 and ARM64, macOS Intel/x64 and Apple Silicon/ARM64.

Windows and Linux packages are unsigned. macOS packages use engineering ad-hoc signing only; they are not Developer ID signed or notarized. Production signing/notarization and updater/self-update remain outside v2.3.

Linux uses Ubuntu 24.04 build hosts on both architectures. Ubuntu 22.04 x64 backward GUI/CLI smoke and all packaged binary compatibility floors must be verified on the final v2.3 candidates; historical v2.2 results do not establish v2.3 package acceptance.

## Release assets

Expected project-defined set, exactly eight files; sizes and hashes are pending final assembly:

- `PlayStoreAppAudit-v2.3.0-windows-x64.zip`
- `PlayStoreAppAudit-v2.3.0-windows-arm64.zip`
- `PlayStoreAppAudit-v2.3.0-linux-x64.zip`
- `PlayStoreAppAudit-v2.3.0-linux-arm64.zip`
- `PlayStoreAppAudit-v2.3.0-macos-x64.zip`
- `PlayStoreAppAudit-v2.3.0-macos-arm64.zip`
- `PlayStoreAppAudit-v2.3.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Extract the ZIP for your OS and architecture before starting the application. The consolidated source archive complements the bundled third-party legal material.

## Verification

**PENDING Phase C/D:** final component freshness, exact frozen main SHA and matching Quality/build/assembly run IDs; six-platform startup, architecture, version, provenance, signing-state and strict legal/source validation; assembled names, sizes and SHA-256; independent public re-download and byte-for-byte verification.

No release tag, final build or publication is claimed by this draft. The latest published release remains v2.2.0. Final publication must upload the accepted existing artifacts without tag-triggered rebuilding.

Optional support: [GitHub Sponsors](https://github.com/sponsors/mrc-labs).
