# Store App Audit usage guide

See the [project README](../README.md) for downloads, platform compatibility and development links. This guide describes the existing GUI, CLI and device workflows.

## Quick start

1. Start the application.
2. Choose a CSV/TSV/TXT package list, select Local APK/package file(s) or a folder, or connect an Android phone and select **Scan Phone**.
3. Confirm the Store country. Availability can differ by country.
4. Select the header **Run** button or **Audit > Run Audit**.
5. Use status chips, search, **View > Quick Filters** or **View > Smart Queries** to inspect results.
6. Select a row to inspect Store/device/local-package evidence in the Details Panel.
7. Export complete or currently visible results from **Audit > Export Results**.

A file may contain a `package_name` column, optionally with an `app_name` column, or one Android package ID per row. `sample_packages.csv` shows the simplest supported CSV format.

### Headless CLI (v2.2 onward)

A Python installation provides `playstore-app-audit-cli`; `playstore-app-audit` remains the Qt GUI command. The CLI does not import the Qt UI or create a `QApplication`. This command replaces the older positional `python -m playstore_app_audit.cli <file>` interface, whose timestamped CSV and separate problems file were based on the retired simple audit path.

In the standalone packages, run the existing executable with `cli` before `audit` from a terminal. No separate Python installation is needed. The normal executable launch still opens the GUI:

```text
Windows (inside the extracted package): .\PlayStoreAppAudit.exe cli audit app-list sample_packages.csv --output results.json
Linux (inside the extracted package):   ./PlayStoreAppAudit cli audit app-list sample_packages.csv --output results.json
macOS (beside the extracted app):        ./PlayStoreAppAudit.app/Contents/MacOS/PlayStoreAppAudit cli audit app-list sample_packages.csv --output results.json
```

```text
playstore-app-audit-cli audit app-list sample_packages.csv --country it --output results.json
playstore-app-audit-cli audit apk-files archive/a.apk archive/b.xapk --format csv --output apks.csv
playstore-app-audit-cli audit apk-folder archive/ --fresh --output folder.json
playstore-app-audit-cli audit phone --country it --output phone.json
```

The source commands are `app-list`, `apk-files`, `apk-folder` and `phone`. All accept `--country`, `--language`, `--workers`, `--fresh`, `--format json|csv`, `--output` and `--force`. Phone additionally accepts `--include-system`; by default its read-only ScanSession excludes system packages. JSON is the default format. Without `--output`, the payload goes to stdout and progress goes to stderr. JSON reuses the versioned GUI result schema; CSV uses the GUI field order and date formatting. Files are written through a temporary sibling and replaced only after a successful audit. An existing output requires `--force`, and an input file cannot be its own output.

The CLI reads relevant saved defaults without saving command-line overrides. `--fresh` bypasses reusable healthy Store results and refreshes the existing alternative-provider path without deleting caches. `--device-provider`, `--device-profile` and `--device-endpoint` select the existing Device Specific provider, built-in or saved Personal Device profile, and validated Custom Dispenser endpoint. Personal Google Session uses an already signed-in session; credentials are never CLI flags. Saved Personal Device profiles work without a connected phone. CLI audits do not write audit history or change Personal Device library records. File locations, raw ADB serials, ScanSession identifiers, secret/auth material and local Personal Device UUIDs are omitted or masked in output. Ctrl+C signals cooperative cancellation and produces no final output.

Explicit Device Specific CLI overrides are validated before the audit. If saved Device Specific defaults have become unavailable, the CLI still completes the public Store audit and leaves those defaults unchanged; Device Specific evidence remains optional.

Exit status is `0` for a completed audit (including ordinary Not Found results), `2` for invalid input/configuration, `3` for runtime failure and `130` for Ctrl+C. Runtime diagnostics are intentionally generic to avoid exposing credentials or device identifiers; progress and completion counts are on stderr.

## Local APK / package workflows

Store App Audit can audit explicit local `.apk`, `.apks`, `.apkm` and `.xapk` files or recursively discover supported package files in a selected folder. Physical artifact identity remains separate from Android package identity, so multiple files for the same package can remain distinct results.

The local-package path reuses the same Store/provider evidence and result presentation used elsewhere while keeping local metadata such as filename, path, label, local version, SHA-256 and SDK information available in the table and Details Panel.

v2.1 extends this workflow with safe physical-file management. It includes single-file **Rename File…** / **Remove File…**, Mass Rename with metadata templates and a complete validation preview, plus **Remove All Outdated…** / **Remove All Unknown…** with permanent-deletion safeguards. Operations remain physical-path based, preserve unrelated Store/audit evidence, keep duplicate package/SHA files independent, and do not rerun the Store audit after filesystem mutation.

The Local APK direction is inspired by the long-retired [LocalAPK](https://github.com/brz/LocalAPK) utility. Store App Audit is an independent implementation; this acknowledgement refers to product inspiration, not shared code or project affiliation.

## Understanding the results

- **Recent:** listing age is at most the configured Recent maximum, 365 days by default.
- **Aging:** listing age falls between the configured thresholds, 366-730 days by default.
- **Stale:** listing age is above the configured Stale threshold, 730 days by default.
- **Not Found:** no listing was found in the configured countries that were successfully checked; this does not prove global removal.
- **Anomaly:** Store responses were unusual, incomplete or could not be classified confidently.

The optional Maintenance Score summarizes maintenance signals from 0 to 100. It is not a malware, security or trust rating. Its methodology is available from **Help > Maintenance Score Methodology**.

Installed and Local APK versions use a conservative relationship model. `Outdated` is reported only when version evidence establishes ordering; staged and device-specific rollouts can still differ from a simple public Store comparison.

## Android phone and ADB support

ADB access is read-only with respect to installed Android apps. Store App Audit can list packages, inspect device/package metadata and open Android's app-details settings screen. It does not install, uninstall, enable, disable or otherwise modify Android apps.

The application can use an existing ADB executable from `PATH`, common Android SDK locations, `ANDROID_SDK_ROOT` or `ANDROID_HOME`. When no compatible ADB is found, supported hosts can offer a managed download of Google's official Android Platform-Tools archive into the application's local data directory.

Managed Platform-Tools support:

- Windows x64 and ARM64 hosts: Windows archive.
- macOS Intel and Apple Silicon hosts: macOS archive.
- Linux x64: Linux archive.
- Linux ARM64: supply a native ARM64-compatible ADB from the operating system/distribution or Android SDK.

USB debugging and device authorization are required. The in-app **ADB Setup Guide** contains troubleshooting instructions.

Standard Scan Phone captures compact package state. Optional Advanced Settings can collect richer device metadata. A successful scan session can be reused by Run, and Store auditing can continue with captured compact data if the phone is later disconnected. Device Inventory history advances only after a successful audit, not merely after scanning.

## Privacy and network behaviour

Imported files, connected-device metadata, settings, cache entries, audit history, inventory history, snapshots and activity logs are processed and stored locally. Store App Audit has no first-party telemetry or analytics service.

Audits are not completely offline: package IDs, Store country and Store language are used in requests to public Google Play endpoints through the application's Store lookup stack. Optional Store icons are downloaded from HTTPS URLs returned by Store metadata and cached locally. Software update checks contact the public GitHub Releases API. A managed ADB installation, when explicitly approved, downloads Google's official Platform-Tools archive.

Diagnostic bundles are created only when explicitly requested and are not uploaded automatically. Logs, reports and diagnostic bundles can contain local or device-related information, so review them before sharing.

## Debug / troubleshooting

Start an explicit source-development debug session with:

```bash
python main.py --debug
```

The session log is written under the active application-data directory in `logs/debug-<timestamp>.log`. The packaged Windows equivalent is:

```text
PlayStoreAppAudit.exe --debug
```

Debug logs are never uploaded automatically and may contain local filesystem paths or filenames.

For cold Local APK performance analysis on a representative folder:

```bash
python tools/profile_local_apk_cold_load.py PATH_TO_APK_FOLDER
```

The profiler uses a temporary empty metadata cache and does not clear the application's normal cache.

