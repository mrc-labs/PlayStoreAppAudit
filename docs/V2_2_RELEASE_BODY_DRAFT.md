# Store App Audit v2.2.0 — unpublished release-body draft

Title: `Store App Audit v2.2.0`. **DRAFT ONLY.** Replace pending verification and compatibility findings with accepted final evidence before publication. Do not use prep diagnostic builds as final candidates.

```markdown
## What's New / Highlights

### Added
- **Personal Device library:** Explicitly save multiple privacy-safe profiles with friendly names; select them offline, refresh, rename or delete them while keeping built-in profiles separate.
- **CLI/headless audits:** Audit App Lists, Local APK files/folders and connected phones with canonical JSON/CSV output, through `playstore-app-audit-cli` or the packaged `cli audit` command.
- Optional GitHub Sponsors support is available in About and repository surfaces.

### Changed
- **Independent Custom layouts:** Custom (Phone / App List) and Custom (Local APK) remember their own columns, order and widths across source switching and restart, with conservative migration from the earlier shared layout.

### Fixed
- Unavailable saved Personal Device selections survive unrelated settings saves without overwriting future-schema profile data.

## Compatibility and distribution
- Version `2.2.0`; Windows File/Product version `2.2.0.0`; stable CPython 3.14 baseline, exact patch **PENDING**.
- Planned packages: Windows x64/ARM64, Linux x64/ARM64 and macOS Intel/Apple Silicon.
- Planned signing state: Windows/Linux unsigned; macOS ad-hoc engineering signed, not Developer ID signed or notarized. Confirm against final evidence before publication.
- Linux builds use Ubuntu 24.04 on both architectures. Final packaged GLIBC/GLIBCXX requirements and x64 Ubuntu 22.04 backward-smoke evidence: **PENDING**. A build baseline alone is not a runtime compatibility guarantee.
- Managed ADB remains read-only. Personal Device persistence is explicit and excludes sensitive identifiers/account credentials; Device Specific evidence remains additive to raw public Store evidence.

## Release assets
- Six platform ZIPs for Windows, Linux and macOS on x64/ARM64.
- `PlayStoreAppAudit-v2.2.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: **PENDING — not selected**.
- Final Quality number/run/exact SHA: **PENDING**.
- Final Windows x64/ARM64 run: **PENDING**.
- Final Linux x64/ARM64 run: **PENDING**.
- Final macOS x64/ARM64 run: **PENDING**.
- Six-package architecture/startup/layout/provenance/legal/source validation and exact eight-file assembly: **PENDING**.
- Final `SHA256SUMS.txt` evidence and independent public re-download/size/hash/byte comparison: **PENDING**.

🍺 Enjoying Store App Audit? [Sponsor its development on GitHub](https://github.com/sponsors/mrc-labs) and help support testing and development tools.
```
