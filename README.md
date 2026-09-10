# Play Store App Audit

*Android App Inventory, Store Analysis & Maintenance Toolkit*

Play Store App Audit is a desktop utility for checking Android package IDs against public Google Play listings. It helps you review Store availability, listing freshness and maintenance signals for an imported app list or the packages installed on an Android phone.

The application uses Qt 6 / PySide6 and is not affiliated with or endorsed by Google.

## Key features

- Import package lists from CSV, TSV or TXT files.
- Scan a connected Android phone through ADB and export its current package inventory.
- Check Google Play availability and update information in a selected Store country.
- Use the connected Android device's active system language automatically for Store metadata, while file/list audits can use the primary language of the selected country.
- Fall back across configurable countries without treating one regional absence as global removal.
- Configure concurrent Store workers from Advanced settings; 16 is the current recommended/default value.
- Show live progress while regional fallback countries are being verified.
- Classify listings as Current, Aging, Stale, Removed, Store anomaly or Other.
- Inspect the selected result in a dedicated Details Panel with Store/device metadata, country/language evidence, previous-audit changes and viewport-based narrow, wide and extra-wide layouts.
- Review grouped changes such as newly installed/removed apps, Store availability changes, reappeared listings, Store version/update changes and maintenance-state transitions.
- Optionally show Play Store app icons beside Store titles.
- Optionally calculate a transparent Maintenance Score heuristic.
- Read friendly Notes consistently in the table, tooltip, Details Panel and HTML report while raw machine-readable Notes remain available in data exports.
- Optionally collect installed version, installer, SDK, install/update and permission metadata from a connected device.
- Filter results with search, status chips and Quick Filters, save one-level All/Any Smart Queries, and restore full result visibility with **View > Clear All Filters**.
- Switch between Basic, Device, Technical and Custom views without mixing result filters with audit configuration.
- Save reusable Audit Presets that affect how the next audit runs without changing result filters or presentation.
- Use conservative smart/incremental re-audit behavior, targeted rechecks or an explicit Force full refresh.
- Compare with a previous audit and inspect snapshots/inventory changes under **Tools > Device History**.
- Export all or visible results as CSV, HTML or versioned JSON from **Audit > Export Results**.
- Follow operational status in the native status bar and audit progress in the results header.

## Road to v2.0

v2.0 is the next planned major release and the return to a full multi-platform distribution. Development, correction, stabilization and packaged acceptance are Windows x64-first. After that implementation is functionally complete and accepted, the final v2.0 cross-platform gate is planned to produce Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Intel/x64 and macOS Apple Silicon/ARM64 builds from the same frozen exact source SHA.

A major v2.0 product pillar is **Local APK analysis**: safely reading standalone APK files from local storage, keeping exact APK artifact identity separate from Android package identity, comparing local artifacts with Store/provider evidence, and building toward a persistent Local APK Library. The v2 development source now contains the parser, typed `LocalArtifact`, package-deduplicated Store fan-out and transient multi-file Local APK Audit workflow. This workflow is development-state functionality and is not part of the current published v1.99.0 release.

The Local APK direction is inspired by the excellent, long-retired [LocalAPK](https://github.com/brz/LocalAPK) utility, which provided a practical way to manage local Android APK collections and is now archived. Play Store App Audit is an independent implementation; this acknowledgement refers to product inspiration, not shared code or project affiliation.

CLI/headless support is planned separately for v2.1 rather than v2.0. See the [Product roadmap](docs/ROADMAP.md) for the current release plan.

## Download and installation

Published builds are available from [GitHub Releases](https://github.com/mrc-labs/PlayStoreAppAudit/releases).

The current published v1.99.0 release is a Windows x64-only build and provides one prebuilt package:

- Windows x64

Download the Windows x64 ZIP, extract it to a normal folder, then start the application from the extracted package.

The Windows v1.99.0 package is intentionally unsigned. v2.0 is the first planned return to multi-platform distribution; production signing is the preferred target but remains contingent on successful credential/provider validation. Microsoft Defender SmartScreen or another reputation-based check may therefore ask you to confirm that you want to run the current package. That warning reflects signing and reputation status, not an application error or a finding that the application is unsafe.

Only Windows x64 is currently published as a v1.99.0 prebuilt. Windows ARM64, Linux x64/ARM64 and macOS Intel/Apple Silicon prebuilt packages are planned to return with v2.0. They are intentionally not built in parallel during normal feature development: Windows x64 is completed and stabilized first, then the other five targets are validated in the final v2.0 cross-platform production gate.

The v1.99.0 release includes one consolidated third-party source archive and a release-wide `SHA256SUMS.txt` alongside the Windows x64 ZIP. All three project-defined assets were validated from frozen source SHA `1065744488e548663e3ba365566a9932837f5fb5` before publication and reverified after download from the [published release](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.99.0).

## Quick start

1. Start the application.
2. Choose a CSV, TSV or TXT package list, or connect an Android phone and select **Scan Phone**.
3. Confirm the Store country. Availability can differ by country, so adjust it when necessary.
4. Select the header **Run** button or **Audit > Run Audit**.
5. Use the status chips, search box, **View > Quick Filters** or **View > Smart Queries** to inspect the results.
6. Select a row to inspect Store/device evidence in the details panel or open the grouped audit-change overview.
7. Export the complete or currently visible results from **Audit > Export Results**.

A file may contain a `package_name` column, optionally with an `app_name` column, or one Android package ID per row. The included `sample_packages.csv` shows the simplest supported CSV format.

## Understanding the results

- **Current:** the listing was updated within the last 365 days.
- **Aging:** the last update was more than 365 and no more than 730 days ago.
- **Stale:** the last update was more than 730 days ago.
- **Removed:** the package was unavailable in the configured countries that were successfully checked.
- **Store anomaly:** Store responses were inconsistent or otherwise unusual.
- **Other:** the check was incomplete, failed or could not be classified confidently.

The optional Maintenance Score summarizes maintenance signals from 0 to 100. It is not a malware, security or trust rating. Its full methodology is available from **Help > Maintenance Score Methodology**.

An installed version that differs from the Store version is reported as a difference, not automatically as outdated. Device-specific variants, staged rollouts and regional releases can legitimately differ.

## Android phone and ADB support

ADB access is read-only in the current application. Play Store App Audit can list packages, inspect device and package metadata, and open Android's own app-details settings screen. It does not install, uninstall, enable, disable or modify Android apps.

The application can use an existing ADB executable from `PATH`, common Android SDK locations, `ANDROID_SDK_ROOT` or `ANDROID_HOME`. When no compatible ADB is found, it can offer to download the official Android Platform-Tools archive into the application's local data directory:

- Windows x64 and ARM64 hosts can use the managed Windows archive.
- Supported macOS hosts can use the managed macOS archive.
- Linux x64 can use the managed Linux archive.
- Linux ARM64 requires a native ADB supplied by the operating system, distribution or an ARM64-compatible Android SDK.

USB debugging and device authorization are required. The in-app **ADB setup guide** contains troubleshooting instructions.

Scan Phone always captures compact installed-app information, including versionCode, installer and enabled state where available. In **Tools > Advanced Settings > Device**, **Collect full device metadata during Scan Phone** optionally captures extended metadata such as installed version, SDK information and timestamps. It defaults to OFF and can significantly increase scan time. Sensitive permissions follow the existing permission-audit setting.

After a successful full Scan, Run reuses the captured metadata even if the phone is disconnected; scan again to capture a newer device state. If extended collection fails, the compact scan remains usable and Run can collect extended data from the matching connected phone. The scan session lasts only until it is replaced or the application closes. Device Inventory comparisons use the compact scan snapshot, and scanning alone does not advance the history baseline.

## Privacy and network behaviour

Imported files, connected-device metadata, settings, cache entries, audit history, inventory history, snapshots and the activity log are processed and stored locally. The application has no first-party telemetry or analytics service.

An audit is not entirely offline: package IDs, the selected country and the Store language are used in requests to public Google Play endpoints through `google-play-scraper` and the HTML fallback. If the optional app-icon setting is enabled, icon images are downloaded from HTTPS URLs returned by Store metadata and cached locally for reuse. A cached icon is retained while the app's Store update marker remains unchanged; when that marker changes, the icon is fetched again. The persistent icon cache is bounded to 512 entries and 64 MiB, while decoded icons use a smaller in-memory LRU for the active session. Disk reads and network downloads populate the already-visible table progressively rather than blocking results display; cached icons remain usable when the network is unavailable. **Check for updates** contacts the public GitHub Releases API. If you approve a managed ADB installation, the application downloads the official Platform-Tools archive from Google's download host.

The activity log is local and records operational events such as startup, a loaded source filename and some failure messages. A diagnostic bundle is created only when you explicitly choose a destination; it is not uploaded automatically. The bundle contains sanitized settings, application/system information, aggregate result counts, available device-summary fields (including a masked serial when present) and the local activity log. Review diagnostic bundles before sharing them.

CSV and HTML reports contain the audit/device fields selected by the application and should likewise be reviewed before distribution.

## Platform support

| Platform | Current published v1.99.0 | Planned v2.0 |
| --- | --- | --- |
| Windows x64 | Windows x64 ZIP | Primary implementation/acceptance platform and final v2.0 build |
| Windows ARM64 | No current prebuilt | Planned in the final v2.0 cross-platform gate |
| Linux x64 | No current prebuilt | Planned in the final v2.0 cross-platform gate |
| Linux ARM64 | No current prebuilt | Planned in the final v2.0 cross-platform gate |
| macOS Intel / x64 | No current prebuilt | Planned in the final v2.0 cross-platform gate |
| macOS Apple Silicon / ARM64 | No current prebuilt | Planned in the final v2.0 cross-platform gate |

The published v1.99.0 Windows x64 package was produced from exact commit `1065744488e548663e3ba365566a9932837f5fb5` after post-merge Quality validation, then assembled and checksum-verified before and after publication.

## License

Play Store App Audit's own code is licensed under the [GNU General Public License version 3 only](LICENSE) (GPL-3.0-only).

GPLv3 permits commercial use provided its terms are followed. An alternative commercial license may be available for organisations or products that need rights beyond GPLv3, such as proprietary redistribution or closed-source integration. See [Commercial licensing](COMMERCIAL-LICENSING.md) and [Licensing model](docs/LICENSING.md).

Third-party components remain under their own licenses. Binary release packages include the applicable third-party notices and source-availability material where required. The v1.99.0 release-wide corresponding-source archive is published alongside the Windows x64 ZIP.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Material contributions require acceptance of the project's [Contributor License Agreement](CLA.md).

## Development

The current source identifies application version `1.99.0`. The latest immutable published release is v1.99.0.

The release-packaging baseline is Python 3.13. Quality CI also exercises Python 3.14 source compatibility.

Install the development dependencies, run the application and execute the quality checks with:

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
- [CI and release maintenance](docs/CI_MAINTENANCE.md)
- [Durable project decisions](docs/PROJECT_DECISIONS.md)
- [Current project status](docs/PROJECT_STATUS.md)
- [Product roadmap](docs/ROADMAP.md)
- [Local APK parser foundation](docs/LOCAL_APK_PARSER.md)
- [v1.99 chat handoff](docs/HANDOFF_V1.99.md)
- [v1.9 release-closure handoff](docs/HANDOFF_V1.9.md)
- [Project guidance for coding agents](AGENTS.md)

## Building from source

Release packages use Python 3.13 and Nuitka standalone packaging. The published v1.99.0 profile used one exact `main` SHA, built only the Windows x64 candidate from that SHA, validated legal/source evidence, assembled the exact three-file Windows x64 release asset set, then tagged and published the already validated artifacts without rebuilding.

The full Windows/Linux/macOS x64/ARM64 production release path is assigned to v2.0. Development and packaged acceptance remain Windows x64-first; Windows ARM64, Linux x64/ARM64 and macOS x64/ARM64 are validated in the final cross-platform production gate. Production signing/notarization remains a preferred target where applicable, but is not promised until provider eligibility, credentials and end-to-end validation are proven. Platform-specific prerequisites, architecture validation, legal/source handling and release procedures are documented in [Building Play Store App Audit](docs/BUILDING.md); current milestone assignment is recorded in [Project decisions](docs/PROJECT_DECISIONS.md) and the [Product roadmap](docs/ROADMAP.md).
