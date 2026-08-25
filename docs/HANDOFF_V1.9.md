# Play Store App Audit v1.9 Closure Handoff

Last updated: 2026-08-25

Status: **v1.9.0 is published, independently verified and immutable. Post-release Actions housekeeping is complete. Active development planning has moved to v1.99; continue from `HANDOFF_V1.99.md`.**

## Closure boundary

This file is the final v1.9 release/closure record. It is not the active development handoff. Read `HANDOFF_V1.99.md` with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md`, `RELEASE_CLOSURE.md` and a freshly generated `REPOSITORY_SNAPSHOT.md` for new work.

Never modify, rebuild, retag or replace v1.9.0, v1.8.0 or any earlier published release. A later documentation-only `main` commit does not change the immutable v1.9 release source SHA.

## Immutable v1.9.0 release

- Version/tag: `v1.9.0`
- Published: `2026-08-25T02:51:42Z`
- URL: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.9.0
- Release ID: `376114171`
- Title: `Play Store App Audit v1.9.0 (Win x64 Only)`
- Profile: intentionally unsigned Windows x64 Engineering Test Build, Nuitka standalone ZIP
- Frozen source SHA: `6c117009525f40434e9db714dadf1dd01b79f9ab`
- Annotated tag object: `e61033f0ffba3d14f598da4d928aa07390dbbfa9`
- Tag peel target: exact frozen source SHA
- Application version: `1.9.0`; Windows File/Product version: `1.9.0.0`
- Quality run: `32797795985`, passed on Python 3.13 and 3.14
- Windows x64 build run: `32798334950`
- Build artifact: ID `9546290578`, `PlayStoreAppAudit-v1.9.0-windows-x64`
- Engineering assembler run: `32801220807`
- Assembler artifact: ID `9546545528`, `PlayStoreAppAudit-v1.9.0-windows-x64-engineering-release-assets`

Published project-defined assets verified after re-download:

- `PlayStoreAppAudit-v1.9.0-windows-x64.zip` — asset ID `528529615` — 33,477,938 bytes — SHA-256 `74db811d959a06709aba4d747873ec1b19894e50ba7183f463f7929b44e19c68`
- `PlayStoreAppAudit-v1.9.0-third-party-sources.tar.xz` — asset ID `528529608` — 73,128,144 bytes — SHA-256 `ccccbd72992bed8692388077fd409dc76bb8f64efce8fa2ef283b74797a4df95`
- `SHA256SUMS.txt` — asset ID `528529607` — 225 bytes — SHA-256 `eb2b5f6d5a8fe978e54367b887c65d77994307447154435e3b3ae81c4bf2bd23`

## Release verification summary

- Canonical build used Python 3.13.15 AMD64, `PySide6-Essentials==6.11.1` and `Nuitka==4.1.3`; 403 pytest tests passed.
- PE AMD64/x64, standalone content, application/Windows version, intentionally unsigned state, startup, legal/source material and exact-SHA provenance checks passed.
- Managed Platform-Tools 37.0.1 was validated; its PE I386 `adb.exe` ran under Windows WOW64 while application ADB behavior remained read-only.
- The exact assembler-produced ZIP passed deterministic startup from a clean extraction with isolated data directories before tagging, and its checksum remained unchanged.
- Publication created the annotated tag only after artifact validation and did not trigger a package rebuild.
- After publication, exactly three public assets were re-downloaded into a fresh directory. Names, byte sizes and hashes matched; `SHA256SUMS.txt` independently validated both payloads.
- The re-downloaded public ZIP passed the clean-extraction deterministic packaged smoke again. Version, AMD64 architecture, unsigned state, provenance and unchanged ZIP hash were reconfirmed.

## Post-release Actions state

Housekeeping run `32805211585` applied the unchanged seven-day generational policy successfully from the frozen SHA.

- No failed/cancelled run, successful run or individual artifact was eligible for deletion.
- Active Actions state: 10 artifacts / 574,199,782 bytes (547.60 MiB).
- Retain canonical v1.9 build artifact `9546290578` and assembler artifact `9546545528` for audit.
- The v1.8 build/assembler generation and two UI-style generations remain inside the documented grace period.
- No manual deletion bypassed policy; published assets, tags, source commits, repository retention and cleanup logic were unchanged.

## Shipped v1.9 product scope

PR `#116` delivered shared friendly Notes presentation and tooltip with raw-data compatibility, **Maintenance Score** user-facing terminology with stable `health_score`, warning foreground colours, About hierarchy, coordinated main-action icons, and the Display Settings populated-table crash/persistence fix.

PR `#117` delivered viewport-based narrow/wide/extra-wide Details responsiveness, preserving 760/680 px hysteresis and adding 1180/1080 px extra-wide hysteresis with Store/Notes, Installed/Changes and Evidence/Diagnostics columns.

PR `#118` delivered one native `QStatusBar` using the same canonical status label and progress widget, active-only progress, an action-only main row, no duplicate source/device identity and no new status/persistence model.

PR `#119` froze version 1.9.0 and release documentation. The subsequent exact-SHA build, assembly, tag, publication, public re-download and smoke verification completed successfully.

## Transition to v1.99

- Current application/source version remains `1.9.0`.
- Active development cycle is v1.99, likely the final Windows x64-only ETB before v2.0.
- `HANDOFF_V1.99.md` is the active self-contained continuation handoff.
- `scripts/export_chat_handoff.ps1` parses numeric handoff versions, so 1.99 sorts newer than 1.9 without a script change.
- Do not generate a continuation ZIP until the closure documentation PR is reviewed, merged, local VS Code `main` is safely synchronized, and the working tree is clean.

Historical v1.8.0 remains immutable at `ac328f0dffddb6b70fa7600f1291377376bc05d4`; its release evidence remains in `HANDOFF_V1.8.md`, `PROJECT_STATUS.md` history and `RELEASE_NOTES.md`.
