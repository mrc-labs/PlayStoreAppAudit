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
- UI: Qt Widgets
- Current application style: forced Fusion
- Windows signing: unsigned
- Linux signing: unsigned
- macOS signing: ad-hoc only, not notarized

## Current workflows

- `.github/workflows/quality.yml`
- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/build-macos-linux.yml`
- `.github/workflows/assemble-release.yml`

The current production-release candidate model is:

- Windows workflow: x64 + ARM64
- combined macOS/Linux workflow: Linux x64 + ARM64 and macOS x64 + ARM64
- assembler: validates all six candidates and emits exactly eight public files

The v1.4 workflow-split PR will replace the combined desktop workflow with separate Linux and macOS workflows and update the assembler to accept three run IDs.

## Current release scripts

- `.github/scripts/assemble_release_assets.py`
- `.github/scripts/build_windows_standalone.ps1`
- `.github/scripts/inspect_pe.py`
- `.github/scripts/legal_payload_store.py`
- `.github/scripts/prepare_release_legal_bundle.py`
- `.github/scripts/release_asset_layout.py`
- `.github/scripts/validate_release_legal_bundle.py`
- `.github/scripts/validate_windows_standalone.py`

No current script has been identified as dead. `prepare_release_legal_bundle.py` and `validate_release_legal_bundle.py` are candidates for later modularization, not deletion.

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

## v1.4 work queue

### P0 - Documentation and persistent context

- Update `AGENTS.md` to the current release/build invariants.
- Add `PROJECT_DECISIONS.md` and `PROJECT_STATUS.md`.
- Correct README distribution text for the six-platform v1.3.0 release.
- Correct `BUILDING.md` and `ARCHITECTURE.md` to the frozen-SHA/six-RC/assembler/eight-asset release model.
- Keep CHANGELOG user-facing and move internal CI/process decisions to engineering docs.
- Audit published GitHub Release descriptions for the same user-vs-maintainer separation.
- Use cheap validation only; no Nuitka build is justified for documentation-only changes.

### P1 - Release workflow isolation

- Replace `.github/workflows/build-macos-linux.yml` with:
  - `.github/workflows/build-linux.yml` using x64 + ARM64 matrix
  - `.github/workflows/build-macos.yml` using x64 + ARM64 matrix
- Keep `.github/workflows/build-windows-exe.yml` x64 + ARM64 matrix.
- Change assembler inputs to `windows_run_id`, `linux_run_id` and `macos_run_id`.
- Preserve exact-SHA enforcement across all three source runs.

### P1 - Cheap legal-material preflight

Add a pre-Nuitka deterministic legal/source prerequisite check covering:

- CPython license resolution
- exact PySide6/Qt version metadata
- official Qt source archive metadata and digests
- expected source archive list
- certifi source material
- other deterministic legal prerequisites already knowable before compilation

The later strict legal gate remains mandatory.

### P1/P2 - Production signing

macOS:

- Developer ID Application signing
- hardened runtime as appropriate
- secure timestamp
- notarization with Apple's current tooling
- staple and Gatekeeper verification
- final ZIP/checksums only after notarization succeeds

Windows:

- select a trusted Authenticode route suitable for direct GitHub ZIP distribution
- keep the private key in compliant hardware/cloud protection or an approved signing service
- use SHA-256 and RFC3161 timestamping
- verify signatures in CI
- do not use self-signed certificates for public distribution

### P2 - Forward compatibility

- Replace APIs already deprecated or scheduled for deprecation when behaviour is understood.
- Evaluate explicitly documented preferred replacements where behaviour is equivalent.
- Do not rewrite stable supported APIs merely because they are old.
- Audit Python 3.14 compatibility while keeping production packaging on Python 3.13 until deliberately migrated.

### P2 - GitHub Actions / Node

- The application itself does not use Node.
- Monitor official GitHub Action majors for their future Node 26 runtime.
- Upgrade action majors when the official actions adopt/support that runtime; do not add `setup-node` just to force Node 26.

### P2 - UI modernization

- Test removing `app.setStyle("Fusion")` and compare native Windows/macOS/Linux styles.
- Audit QSS that overrides native appearance, especially scrollbar styling.
- Check dark/light palettes, high-DPI behaviour, hover/disabled/focus states, tables/headers, spacing and keyboard/focus behaviour.
- Preserve semantic app colours.
- Evaluate native platform style before adding a theme dependency.
- Keep Qt Widgets unless a demonstrated reason justifies migration.

## Known v1.3 release lessons

- Deterministic legal/source failures should be caught before expensive compilation where possible.
- Compiler success alone is not release evidence; package, architecture, startup, legal and provenance validation remain mandatory.
- Release artifacts from different source SHAs must never be mixed.
- Platform workflow isolation should improve selective reruns without weakening one-SHA release identity.

## Maintenance checkpoint

The first v1.4 maintenance PR is documentation/context-only. Subsequent workflow, legal preflight, signing, API and UI work should remain in separate controlled PRs.
