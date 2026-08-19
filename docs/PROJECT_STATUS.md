# Project Status

Last updated: 2026-08-19

## Current release

- Version: `v1.3.0`
- Release commit: `fb2193dfc13d0f0e6b7be660c1342bbf87d26081`
- State: published, latest, not prerelease
- Release history/assets: immutable
- Public assets: exactly 8
- Prebuilt platforms: Windows x64/ARM64, Linux x64/ARM64, macOS x64/ARM64

v1.3.0 must not be rebuilt, retagged, rewritten or have its published binary assets replaced as part of v1.4 maintenance.

## Current baselines

- Packaging Python: 3.13
- Quality Python: 3.13 + 3.14
- `PySide6-Essentials`: 6.11.1
- Nuitka: 4.1.3
- UI technology: Qt Widgets
- v1.4 application style policy: Qt platform/default QStyle; no global forced Fusion
- Windows v1.3 signing: unsigned
- Linux v1.3 signing: unsigned
- macOS v1.3 signing: ad-hoc only, not notarized
- macOS v1.4 production path: Developer ID + hardened runtime + secure timestamp + notarization/stapling/Gatekeeper implemented; real credential-backed validation still pending
- Windows v1.4 production path: Microsoft Artifact Signing Public Trust + SHA-256/RFC3161 + native x64/ARM64 post-sign verification implemented; real Azure credential/profile-backed validation still pending

## Current workflows

- `.github/workflows/quality.yml`
- `.github/workflows/ui-style-audit.yml`
- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/sign-windows.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`
- `.github/workflows/assemble-release.yml`

Production release candidates remain exact-SHA guarded and manually dispatched. Windows native x64/ARM64 builds pass through the dedicated production signing workflow; Linux and macOS each build x64/ARM64; the assembler accepts the signed Windows run plus distinct Linux/macOS run IDs and emits exactly eight public files.

The UI style audit is source/render validation only and never builds release packages.

## Current release and audit scripts

- `.github/scripts/assemble_release_assets.py`
- `.github/scripts/build_windows_standalone.ps1`
- `.github/scripts/capture_ui_style.py`
- `.github/scripts/inspect_pe.py`
- `.github/scripts/legal_payload_store.py`
- `.github/scripts/preflight_release_legal_material.py`
- `.github/scripts/prepare_release_legal_bundle.py`
- `.github/scripts/release_asset_layout.py`
- `.github/scripts/sign_macos_app.py`
- `.github/scripts/validate_release_legal_bundle.py`
- `.github/scripts/validate_windows_standalone.py`

No current release script has been identified as dead. `prepare_release_legal_bundle.py` and `validate_release_legal_bundle.py` are candidates for later modularization, not deletion.

## Release invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits.
- Published release history is immutable.
- All six production packages derive from one exact frozen SHA.
- No public RC tag and no tag-triggered binary rebuild.
- Public asset model is exactly six platform ZIPs + one consolidated third-party source archive + one `SHA256SUMS.txt`.
- Linux production packaging remains standalone with replaceable Qt/PySide/Shiboken shared libraries.
- Strict legal validation remains mandatory.
- Managed ADB remains read-only with respect to installed Android apps.

See `PROJECT_DECISIONS.md` and `BUILDING.md` for rationale and procedure.

## v1.4 progress

### Documentation and persistent context

Completed in PR #24:

- refreshed `AGENTS.md`
- added `PROJECT_DECISIONS.md` and `PROJECT_STATUS.md`
- corrected README six-platform v1.3.0 distribution text
- corrected `BUILDING.md` and `ARCHITECTURE.md` release model
- cleaned CHANGELOG maintainer-only process details

Still open outside repository-content changes:

- edit published GitHub Release descriptions where maintainer-only pipeline notes remain when a release-write connector/action is available
- delete merged short-lived remote branches when branch-delete capability is available

Neither housekeeping item justifies changing v1.3.0 binaries, tags or release history.

### Release workflow isolation

Completed in PR #25:

- separate Linux x64/ARM64 workflow
- separate macOS x64/ARM64 workflow
- Windows x64/ARM64 workflow retained
- assembler uses `windows_run_id`, `linux_run_id` and `macos_run_id`
- exact-SHA verification retained across all source runs

No heavy package build was launched merely to validate the workflow split.

### Cheap legal-material preflight

Completed in PR #26. It runs before Nuitka and resolves deterministic CPython, PySide6/Shiboken, Qt source metadata/digests, certifi source metadata and Nuitka legal prerequisites using the canonical legal resolver. It intentionally avoids large Qt/PySide source downloads. The later package-aware source download, legal injection and strict final validation remain mandatory.

### Production signing

macOS implementation merged in PR #27:

- engineering vs production modes
- Developer ID signing inside-out
- hardened runtime and secure timestamp
- accepted notarization required
- staple/signature/Gatekeeper verification before final ZIP
- strict legal evidence refreshed against final signed/stapled app
- only production mode emits canonical release-candidate artifact names

Windows implementation merged in PR #28:

- native x64/ARM64 compilation remains separate from signing
- dedicated signing workflow accepts only a successful exact-SHA Windows build
- Microsoft Artifact Signing Public Trust through GitHub OIDC
- only owned top-level `PlayStoreAppAudit.exe` is signed
- SHA-256 + RFC3161 required
- non-target files hash-guarded
- strict legal evidence refreshed after signing
- final x64/ARM64 ZIPs signature-verified and smoke-tested on native runners
- assembler rejects unsigned Windows build runs

Credential-backed production validation remains pending for both platforms and should be run deliberately only after the required Apple/Azure resources and secrets are provisioned.

### Forward compatibility

Completed in PR #29. No first-party migration candidate met the policy of documented deprecation/supersession plus behaviour-equivalent replacement. A curated regression sentinel now guards the deprecated/superseded APIs reviewed in the sweep. Python 3.14 remains a Quality target while production packaging remains on Python 3.13.

### UI modernization

PR #30 added the cross-platform native-vs-Fusion evidence harness. The validated Qt/PySide 6.11.1 audit found:

- Windows default style: `windows11`; platform plugin: `windows`; native and Fusion renders differ.
- macOS default style: `macos`; platform plugin: `cocoa`; native and Fusion renders differ.
- Linux hosted/Xvfb default style: `fusion`; platform plugin: `xcb`; default and explicit-Fusion renders are byte-identical.
- Windows/macOS native plain controls look more platform-appropriate than Fusion, especially checkbox/radio, combo-box, slider/progress and scrollbar treatment.
- The real application changes less because broad `BaseWindow` QSS overrides many generic control visuals.

PR #31 adopts the resulting style policy:

- remove `app.setStyle("Fusion")`
- let Qt select the platform/default style
- add a regression guard against globally forcing a QStyle again
- validate the change with Quality on Python 3.13/3.14 plus the full Windows/macOS/Linux render audit

Next UI step, in a separate PR:

- narrow generic QSS that masks native presentation, starting with the global font rule and `QScrollBar` override
- preserve semantic status colours, branded primary actions and layout-critical rules
- re-run the render audit before considering any theme dependency

Qt Widgets remains the UI technology. The audit gives no reason to migrate to QML or add a theme framework.

### GitHub Actions / Node

The application itself does not use Node. Monitor official action majors for their future Node 26 runtime and upgrade only when the official actions adopt/support it. Do not add `setup-node` merely to force Node 26.

## Known v1.3 release lessons

- Catch deterministic legal/source failures before expensive compilation where possible.
- Compiler success alone is not release evidence; package, architecture, startup, legal and provenance validation remain mandatory.
- Never mix release artifacts from different source SHAs.
- Platform workflow isolation must not weaken one-SHA release identity.

## Maintenance checkpoint

PR #24 established durable project context, PR #25 split desktop release workflows, PR #26 added legal preflight, PR #27 implemented macOS production trust, PR #28 implemented Windows production trust, PR #29 completed the proactive API sweep, PR #30 added cross-platform UI style evidence and PR #31 adopts platform/default Qt styling. Remaining controlled work includes targeted QSS narrowing, credential-backed signing validation and future official-action Node-runtime monitoring.
