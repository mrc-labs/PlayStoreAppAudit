# Play Store App Audit

Play Store App Audit is a desktop utility for checking Android package IDs against public Google Play listings. It helps you review Store availability, listing freshness and maintenance signals for an imported app list or the packages installed on an Android phone.

The application uses Qt 6 / PySide6 and is not affiliated with or endorsed by Google.

## Key features

- Import package lists from CSV, TSV or TXT files.
- Scan a connected Android phone through ADB and export its current package inventory.
- Check Google Play availability and update information in a selected Store country.
- Fall back across configurable countries without treating one regional absence as global removal.
- Classify listings as Current, Aging, Stale, Removed, Store anomaly or Other.
- Optionally calculate a transparent Health Score maintenance heuristic.
- Optionally collect installed version, installer, SDK, install/update and permission metadata from a connected device.
- Filter results, combine status filters and switch between Basic, Device, Technical and Custom views.
- Compare with a previous audit and maintain device inventory history and snapshots.
- Export all or visible results as CSV or HTML.

## Download and installation

Published builds are available from [GitHub Releases](https://github.com/mrc-labs/PlayStoreAppAudit/releases). This branch contains unreleased v1.2.0 source; do not expect a v1.2.0 download until that release is published.

The normal prebuilt distribution target is Windows x64. Download the Windows x64 ZIP from the release you want, extract it to a normal folder and run `PlayStoreAppAudit.exe` from the extracted package. Windows builds are currently unsigned, so Microsoft Defender SmartScreen or another reputation-based check may ask you to confirm that you want to run the file. That warning reflects signing and reputation status, not a finding that the application is unsafe.

Windows ARM64 remains an explicit manual engineering build capability. macOS and Linux remain supported from the shared source tree, with packaging performed manually or on demand. For historical context, v1.0.0 was the last release that provided six prebuilt packages across Windows, macOS and Linux architectures.

## Quick start

1. Start the application.
2. Choose a CSV, TSV or TXT package list, or connect an Android phone and select **Scan phone**.
3. Confirm the Store country. Availability can differ by country, so adjust it when necessary.
4. Select **Run audit**.
5. Use the status chips, search box and view presets to inspect the results.
6. Export the complete or currently visible results from the export menu.

A file may contain a `package_name` column, optionally with an `app_name` column, or one Android package ID per row. The included `sample_packages.csv` shows the simplest supported CSV format.

## Understanding the results

- **Current:** the listing was updated within the last 365 days.
- **Aging:** the last update was more than 365 and no more than 730 days ago.
- **Stale:** the last update was more than 730 days ago.
- **Removed:** the package was unavailable in the configured countries that were successfully checked.
- **Store anomaly:** Store responses were inconsistent or otherwise unusual.
- **Other:** the check was incomplete, failed or could not be classified confidently.

The optional Health Score summarizes maintenance signals from 0 to 100. It is not a malware, security or trust rating. Its full methodology is available from **Help → Health score methodology**.

An installed version that differs from the Store version is reported as a difference, not automatically as “outdated.” Device-specific variants, staged rollouts and regional releases can legitimately differ.

## Android phone and ADB support

ADB access is read-only in the current application. Play Store App Audit can list packages, inspect device and package metadata, and open Android's own app-details settings screen. It does not install, uninstall, enable, disable or modify Android apps.

The application can use an existing ADB executable from `PATH`, common Android SDK locations, `ANDROID_SDK_ROOT` or `ANDROID_HOME`. When no compatible ADB is found, it can offer to download the official Android Platform-Tools archive into the application's local data directory:

- Windows x64 and ARM64 hosts can use the managed Windows archive.
- Supported macOS hosts can use the managed macOS archive.
- Linux x64 can use the managed Linux archive.
- Linux ARM64 requires a native ADB supplied by the operating system, distribution or an ARM64-compatible Android SDK.

USB debugging and device authorization are required. The in-app **ADB setup guide** contains troubleshooting instructions.

## Privacy and network behaviour

Imported files, connected-device metadata, settings, cache entries, audit history, inventory history, snapshots and the activity log are processed and stored locally. The application has no first-party telemetry or analytics service.

An audit is not entirely offline: package IDs, the selected country and the Store language are used in requests to public Google Play endpoints through `google-play-scraper` and the HTML fallback. **Check for updates** contacts the public GitHub Releases API. If you approve a managed ADB installation, the application downloads the official Platform-Tools archive from Google's download host.

The activity log is local and records operational events such as startup, a loaded source filename and some failure messages. A diagnostic bundle is created only when you explicitly choose a destination; it is not uploaded automatically. The bundle contains sanitized settings, application/system information, aggregate result counts, available device-summary fields (including a masked serial when present) and the local activity log. Review diagnostic bundles before sharing them.

CSV and HTML reports contain the audit/device fields selected by the application and should likewise be reviewed before distribution.

## Platform support

| Platform | Source support | Prebuilt policy |
| --- | --- | --- |
| Windows x64 | Supported | Normal release target; automatic build after relevant pushes to `main` |
| Windows ARM64 | Supported | Explicit manual engineering build |
| macOS | Supported | Manual/on-demand packaging |
| Linux | Supported | Manual/on-demand packaging; Linux ARM64 requires native ADB |

All platforms use the same source tree. Platform-specific behavior is kept behind the application's platform and device layers.

## License status

No project license has been granted yet. Until a license is selected and published, the source is provided without permission to use, copy, modify or redistribute it beyond rights that may apply independently under law. Licensing will be finalized before the repository is made public.

Third-party dependency licensing will be reviewed separately before public publication.

## Development

The release-build baseline is Python 3.13. Install the development dependencies, run the application and execute the quality checks with:

```bash
python -m pip install -r requirements-dev.txt
python main.py
python -m compileall playstore_app_audit
python -m pytest
ruff check playstore_app_audit tests main.py
```

Developer references:

- [Architecture](docs/ARCHITECTURE.md)
- [Building and release workflow](docs/BUILDING.md)
- [Project guidance for coding agents](AGENTS.md)

## Building from source

Windows release packaging uses Nuitka standalone mode with the PySide6 plugin. On Windows x64, `build_windows_exe.bat` creates and validates a versioned standalone package using Python 3.13. Platform-specific prerequisites, architecture validation, signing status and the release lifecycle are documented in [Building Play Store App Audit](docs/BUILDING.md).
