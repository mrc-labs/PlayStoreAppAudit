# Changelog

All notable user-facing and maintenance changes to Play Store App Audit are recorded here.

## [1.1.0] - 2026-08-17

### Added

- A compact Recent sources chevron beside Choose file, synchronized with File → Recent sources.
- File → Run Play Store audit, routed through the same pause-aware audit command as the main Run button.
- A focused Export results submenu containing all/visible CSV and HTML result exports.
- Reusable native rich-help dialogs for the ADB setup and app-list import guides.
- Focused UI, menu, help, icon and Windows-workflow regression coverage.

### Changed

- Application and project metadata versions are now 1.1.0.
- The redundant large in-content product heading has been removed from the final MainWindow while retaining the compact explanatory subtitle.
- The embedded application icon now trims excessive transparent padding without changing or resampling its visible artwork pixels.
- The app-list guide is reorganized around importing CSV/TSV/TXT sources, Recent sources, drag-and-drop, ADB generation and phone-only alternatives.
- Normal Windows builds and the default manual Windows target now build x64 only; ARM64 remains available only as an explicit manual engineering target.
- Superseded Quality workflow runs for the same pull request can be cancelled without affecting other pull requests.

### Removed

- The LinkedIn link and its unused URL constant from the About dialog implementation.

### Compatibility

- The v1.1.0 prebuilt release target is Windows x64 only.
- v1.0.0 remains the last release with the full six-package Windows, Linux and macOS prebuilt matrix.
- Source-level Windows ARM64, Linux and macOS support remains in the shared codebase; their packaging workflows and platform abstractions were not removed.

## [1.0.0] - 2026-08-17

### Added

- Cross-platform runtime abstraction for application data, Store-country detection and Android Platform-Tools paths.
- Portable-mode data-path handling in the canonical platform layer.
- Bulk Android package metadata collection through one read-only `dumpsys package` request, with conservative per-package fallback.
- Canonical immutable Qt table schema in `playstore_app_audit/ui/schema.py`.
- Explicit UI behaviour hooks for row classification, cache loading and device metadata collection/enrichment.
- Regression coverage for country parsing, version comparison, Android compatibility labels, Health score, filters, portable paths, ADB bulk parsing, architecture constraints and UI schema integrity.
- Lightweight pull-request quality workflow covering compile, tests, Ruff and Qt offscreen smoke checks.
- Manual Linux and macOS packaging workflows with platform-specific runtime validation.
- Native Windows ARM64 application packaging alongside the Windows x64 package.

### Changed

- Application version is now 1.0.0 across the package and project metadata.
- State/settings/cache/history code now uses `services.state` directly; the temporary persistence compatibility shim has been removed.
- Historical `v7`/`v8`/`v9`, `qt_base`, `features` and `user_state` module aliases have been replaced by descriptive imports.
- Table columns, labels, widths and export extras no longer depend on UI import order.
- Cross-module runtime monkey-patching for audit selection, classification, cache bypass and ADB enrichment has been replaced by explicit overridable methods.
- Device metadata collection can avoid hundreds of individual `dumpsys package <package>` subprocesses on large app inventories.
- Service/report version strings now follow the package version rather than historical 0.9.x literals.
- Linux CI installs the EGL/X11 libraries required by Qt on the hosted runner.
- macOS packaging excludes the unused Qt Virtual Keyboard platform-input-context plugin.
- macOS/Linux packaging now validates the actual generated binary/app bundle so a deployment-tool false positive cannot upload an empty artifact.
- Release packaging now covers Windows x64 and ARM64, Linux x64 and ARM64, and macOS Apple Silicon and Intel from the same source revision.
- Windows packaging validates native Python/PySide6 inputs; packaging asserts actual PE/ELF/Mach-O architecture, runs deterministic source and packaged smoke tests, and records release provenance in `BUILD-INFO`.
- ADB validation is architecture-aware: each supported managed or native path must execute successfully, while Windows records the downloaded `adb.exe` architecture separately from the native application package.

### Fixed

- MainWindow no longer mutates platform, state or version modules at import time.
- Final source controls are no longer rebuilt twice during window construction.
- Saved Qt header state is invalidated once for the canonical table schema.
- Google Play `datePublished` is not accepted as a latest-update date.
- ADB subprocesses no longer flash console windows on Windows.
- The macOS deployment path no longer attempts to bundle the unused `QtVirtualKeyboardQml` framework through `platforminputcontexts`.
- The Linux Qt smoke/build workflow now provides `libEGL` and related XCB runtime libraries.

### Compatibility

- Windows remains the primary automatic release build.
- Linux and macOS use the same Qt/PySide6 source tree and are manual/on-demand release targets.
- CustomTkinter remains retired and preserved only by the historical `legacy-customtkinter-v9.3` tag.
- The v1.0.0 release matrix targets Windows x64, native Windows ARM64, Linux x64, Linux ARM64, macOS ARM64 / Apple Silicon and macOS x64 / Intel packages.
- The GitHub-hosted Windows ARM64 runner is currently public preview; Windows packages are unsigned, while macOS packages are ad-hoc signed but not Apple-notarized.

## [0.11.0] - 2026-08-16

### Changed

- Flattened the application into the canonical `playstore_app_audit/` package.
- Retired version-suffixed top-level Qt modules and obsolete Tkinter launchers.
- Established `main.py` / `playstore_app_audit.app` as the canonical application entry point.
- Adopted PySide6 Essentials with the Nuitka-based `pyside6-deploy` release path.
