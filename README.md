# Play Store App Audit

The project now has two parallel Windows GUI branches built on the same Play Store audit engine:

- `qt6` — PySide6 / Qt 6 interface, richer table model and native per-monitor HiDPI handling.
- `customtkinter` — CustomTkinter interface, lighter executable and more direct continuation of the previous Tkinter architecture.

`main` is kept as the common/historical base while the two UI variants are compared.

## Shared functional policy

Both comparison branches use the same intended behaviour:

- Google Play `Country` is detected from Windows Region and remains editable.
- Store language is hidden from the UI and fixed internally to `en`.
- `Exclude system apps when loading / scanning` is visible directly in `App source`.
- With ADB and the exclusion enabled, third-party packages are loaded with `adb shell pm list packages -3`.
- With CSV/TSV and the exclusion enabled, system packages are removed during file load when they can be classified.
- `Hide system apps` remains a result-table display filter when system apps were loaded.
- Criticality colours, date thresholds, Store anomaly handling, filtering, export and ADB installation behaviour remain aligned.

## Branch builds

### Qt6

Branch: `qt6`

Artifact: `PlayStoreAppAudit-Windows-Qt6`

Executable: `PlayStoreAppAudit-Qt6.exe`

### CustomTkinter

Branch: `customtkinter`

Artifact: `PlayStoreAppAudit-Windows-CustomTkinter`

Executable: `PlayStoreAppAudit-CustomTkinter.exe`

Each branch contains its own GitHub Actions workflow configuration and local build/run scripts.
