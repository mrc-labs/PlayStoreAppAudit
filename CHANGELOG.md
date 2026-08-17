# Changelog

Notable user-facing and compatibility changes to Play Store App Audit are recorded here.

## [1.2.0] - Unreleased

### Added

- A split **Scan phone** control with direct access to exporting the current phone package inventory as CSV.
- A detailed rich-text guide explaining the optional Health Score methodology and its limitations.
- The application version in the About dialog and in support diagnostics.

### Changed

- Reorganized the File, Tools and Help menus so source actions, result actions, maintenance commands and guidance are easier to find.
- Switched Windows release packaging from a one-file executable to a validated Nuitka standalone ZIP with explicit runtime-content checks and a SHA-256 sidecar.
- Separated **Clear current results** from persistent cache and audit-history maintenance.
- Grouped cache and previous-audit clearing under **Tools → Data maintenance**.
- Kept phone-package export enabled only while a current phone inventory is available.
- Adopted `GPL-3.0-only` for the public project, with alternative commercial licensing available separately and a CLA-based contribution policy.

### Compatibility

- Windows x64 remains the normal prebuilt release target.
- Windows ARM64 remains an explicit manual engineering build capability.
- Windows, macOS and Linux continue to share the same supported source tree; macOS and Linux packaging remains manual/on demand.

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

- Changed the normal prebuilt release policy to Windows x64 only.
- Kept Windows ARM64, Linux and macOS support in the shared source tree and retained manual engineering packaging for those targets.
- v1.0.0 remains the last release with the six-package Windows, Linux and macOS prebuilt matrix.

## [1.0.0] - 2026-08-17

### Added

- The first stable Qt 6 / PySide6 desktop release.
- CSV, TSV and TXT package-list imports with Google Play availability and latest-update checks.
- Multi-country fallback checks that distinguish regional absence from broader unavailability or inconclusive results.
- Current, Aging, Stale, Removed, Store anomaly and Other result classifications.
- Optional Health Score maintenance guidance, previous-audit comparison and configurable technical views.
- Read-only ADB package scanning, installed-device metadata, device summaries, inventory history and snapshots.
- CSV and HTML reports, phone-inventory export and portable-mode data storage.
- A shared Windows, macOS and Linux source tree with prebuilt packages for Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Apple Silicon and macOS Intel.

### Changed

- Adopted the canonical `playstore_app_audit` package and `main.py` entry point for the stable application.
- Improved large-device audit performance by collecting Android package metadata in bulk where available.

### Fixed

- Restricted latest-update parsing to update-specific fields and visible **Updated on** text; original publication dates are not treated as updates.
- Hid ADB subprocess console windows on Windows.
- Added architecture and packaged-startup validation to release builds.

### Compatibility

- Windows was the primary automatic build; macOS and Linux packages were built on demand from the same revision.
- Windows and Linux packages were unsigned. macOS packages were ad-hoc signed for bundle integrity but not Apple-notarized.
- The former CustomTkinter application was retired and retained only at the historical `legacy-customtkinter-v9.3` tag.

## [0.11.0] - 2026-08-16

### Changed

- Consolidated the application into the canonical `playstore_app_audit` package.
- Retired version-suffixed Qt modules and obsolete Tkinter launchers.
- Established `main.py` / `playstore_app_audit.app` as the application entry point.
- Adopted PySide6 Essentials and the Nuitka-based `pyside6-deploy` packaging route.
