# Changelog

Notable user-facing and compatibility changes to Play Store App Audit are recorded here. Internal CI/release-process decisions belong in `AGENTS.md`, `docs/PROJECT_DECISIONS.md` and `docs/BUILDING.md`.

## [1.4.0] - 2026-08-19

### Changed

- Let Qt use the platform-default application style instead of forcing Fusion globally.
- Let native platform styling own the default application font and generic scrollbar presentation.
- Retained the existing semantic colours, branded actions, table treatment and layout while improving native Windows and macOS control integration.

### Compatibility

- v1.4.0 is published as an Engineering Test Build (ETB) for Windows x64 with one prebuilt x64 ZIP package.
- The Windows v1.4.0 package is intentionally unsigned. v1.5.0 remains an unsigned Windows x64 Engineering Test Build; production code signing and the full six-platform production profile move to v1.6.
- Windows ARM64, Linux and macOS remain supported by the shared source tree, but v1.4.0 does not publish new prebuilt packages for those targets.
- The release includes one consolidated third-party source archive and one release-wide `SHA256SUMS.txt` alongside the Windows x64 package.
- Python 3.13 remains the release-packaging baseline; Python 3.13 and 3.14 remain Quality CI targets.

## [1.3.0] - 2026-08-19

### Changed

- Added prebuilt release packages for Windows, Linux and macOS on both x64 and ARM64.
- Consolidated third-party corresponding-source delivery into one release-wide source archive with one `SHA256SUMS.txt`.
- Updated the packaged Qt/PySide baseline to PySide6 Essentials 6.11.1.

### Fixed

- Improved compatibility with current Qt filtering APIs.
- Improved the reliability of third-party license/source material included with release packages.
- Preserved managed ADB support while keeping Android Platform-Tools outside the shipped application runtime.

### Compatibility

- v1.3.0 provides Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 ZIP packages.
- Python 3.13 remains the release-packaging baseline.
- Windows packages are unsigned. macOS packages use an ad-hoc signature and are not Apple-notarized.
- Linux packages use a standalone directory layout inside the ZIP.

## [1.2.0] - 2026-08-17

### Added

- A split **Scan phone** control with direct access to exporting the current phone package inventory as CSV.
- A detailed rich-text guide explaining the optional Health Score methodology and its limitations.
- The application version in the About dialog and in support diagnostics.

### Changed

- Reorganized the File, Tools and Help menus so source actions, result actions, maintenance commands and guidance are easier to find.
- Changed the Windows x64 prebuilt package from a one-file executable to a standalone ZIP.
- Separated **Clear current results** from persistent cache and audit-history maintenance.
- Grouped cache and previous-audit clearing under **Tools > Data maintenance**.
- Kept phone-package export enabled only while a current phone inventory is available.
- Adopted `GPL-3.0-only` for the public project, with alternative commercial licensing available separately and a CLA-based contribution policy.

### Compatibility

- v1.2.0 provides a prebuilt Windows x64 ZIP.
- Windows v1.2.0 is unsigned.
- Windows ARM64, macOS and Linux remain supported by the shared source tree but were not published as v1.2.0 prebuilt release assets.

## [1.1.0] - 2026-08-17

### Added

- A compact **Recent sources** menu beside **Choose file**, synchronized with the File menu.
- File-menu access to running an audit and exporting all or visible results as CSV or HTML.
- Rich in-app guides for ADB setup and CSV/TSV/TXT package-list imports.

### Changed

- Made the source area more compact while retaining the two file/phone input choices and source status.
- Improved application-icon presentation without changing the visible artwork.
- Simplified the About dialog by removing the LinkedIn link.

### Compatibility

- v1.1.0 provides a prebuilt Windows x64 package.
- v1.0.0 remains available for the previously published Windows ARM64, Linux and macOS packages.

## [1.0.0] - 2026-08-17

### Added

- The first stable Qt 6 / PySide6 desktop release.
- CSV, TSV and TXT package-list imports with Google Play availability and latest-update checks.
- Multi-country fallback checks that distinguish regional absence from broader unavailability or inconclusive results.
- Current, Aging, Stale, Removed, Store anomaly and Other result classifications.
- Optional Health Score maintenance guidance, previous-audit comparison and configurable technical views.
- Read-only ADB package scanning, installed-device metadata, device summaries, inventory history and snapshots.
- CSV and HTML reports, phone-inventory export and portable-mode data storage.
- Prebuilt packages for Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Apple Silicon and macOS Intel.

### Changed

- Adopted the canonical `playstore_app_audit` package and `main.py` entry point for the stable application.
- Improved large-device audit performance by collecting Android package metadata in bulk where available.

### Fixed

- Restricted latest-update parsing to update-specific fields and visible **Updated on** text; original publication dates are not treated as updates.
- Hid ADB subprocess console windows on Windows.
- Added packaged architecture and startup validation.

### Compatibility

- Windows and Linux v1.0.0 packages are unsigned.
- macOS v1.0.0 packages are ad-hoc signed for bundle integrity but not Apple-notarized.
- The former CustomTkinter application was retired and retained only at the historical `legacy-customtkinter-v9.3` tag.

## [0.11.0] - 2026-08-16

### Changed

- Consolidated the application into the canonical `playstore_app_audit` package.
- Retired version-suffixed Qt modules and obsolete Tkinter launchers.
- Established `main.py` / `playstore_app_audit.app` as the application entry point.
- Adopted PySide6 Essentials and the Nuitka-based `pyside6-deploy` packaging route.
