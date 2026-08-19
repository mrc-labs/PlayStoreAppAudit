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
- Windows v1.3 signing: unsigned
- Linux v1.3 signing: unsigned
- macOS v1.3 signing: ad-hoc only, not notarized
- macOS v1.4 production path: Developer ID + hardened runtime + secure timestamp + notarization/stapling/Gatekeeper implemented in workflow code; real credential-backed production validation still pending

## Current workflows

- `.github/workflows/quality.yml`
- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`
- `.github/workflows/assemble-release.yml`

The production release-candidate model is:

- Windows workflow: x64 + ARM64
- Linux workflow: x64 + ARM64
- macOS workflow: x64 + ARM64
- assembler: accepts distinct Windows/Linux/macOS run IDs, validates all six candidates and emits exactly eight public files

All three package workflows remain manual and exact-SHA guarded. Splitting Linux and macOS improves isolation and selective reruns without changing the one-SHA release invariant.

## Current release scripts

- `.github/scripts/assemble_release_assets.py`
- `.github/scripts/build_windows_standalone.ps1`
- `.github/scripts/inspect_pe.py`
- `.github/scripts/legal_payload_store.py`
- `.github/scripts/preflight_release_legal_material.py`
- `.github/scripts/prepare_release_legal_bundle.py`
- `.github/scripts/release_asset_layout.py`
- `.github/scripts/sign_macos_app.py`
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

Completed in PR #24 except for the separate audit/edit of published GitHub Release descriptions, which requires release-write access rather than repository-content access.

Completed repository work:

- refreshed `AGENTS.md`
- added `PROJECT_DECISIONS.md` and `PROJECT_STATUS.md`
- corrected README six-platform v1.3.0 distribution text
- corrected `BUILDING.md` and `ARCHITECTURE.md` release model
- cleaned CHANGELOG maintainer-only process details

### P1 - Release workflow isolation

Completed in PR #25:

- separate `.github/workflows/build-linux.yml` x64 + ARM64 matrix
- separate `.github/workflows/build-macos.yml` x64 + ARM64 matrix
- Windows x64 + ARM64 workflow retained
- assembler inputs changed to `windows_run_id`, `linux_run_id` and `macos_run_id`
- exact-SHA verification retained across all source runs

Heavy package validation was deliberately not triggered merely to prove the workflow-file split. Targeted workflow tests and normal Quality CI passed before merge.

### P1 - Cheap legal-material preflight

Completed in PR #26:

- runs after release dependencies are installed and before Nuitka compilation
- requires installed `PySide6-Essentials` to match the exact project pin and requires matching `shiboken6`
- resolves official Qt/PySide metadata and SHA-256 provenance for `pyside-setup`, `qtbase`, `qtimageformats` and `qtsvg`
- resolves certifi source-distribution metadata and digest
- resolves/validates the CPython license using the same exact-version fallback as the strict legal tooling
- verifies required Nuitka legal files and the 4.1.3 release pin
- downloads metadata and small legal text only, not the large Qt/PySide source archives

The later package-aware source download, legal injection and strict legal validation remain mandatory and unchanged.

### P1/P2 - Production signing

macOS implementation is present in the current v1.4 signing PR:

- explicit engineering vs production workflow modes
- production credentials fail closed before dependency installation/build work
- Developer ID certificate imported into a temporary runner keychain
- nested Mach-O/bundle signing inside-out
- hardened runtime and secure timestamp
- Apple notarization must return `Accepted`
- staple, signature verification and Gatekeeper checks occur before final ZIP creation
- strict legal evidence is refreshed/validated against the final signed/stapled app
- only production mode emits canonical macOS release-candidate artifact names
- engineering mode remains ad-hoc and emits non-canonical artifact names

Still required before calling production macOS signing validated:

- provision the documented GitHub Secrets with real Apple credentials
- run one deliberate production build for both architectures
- confirm Developer ID, notarization, staple and Gatekeeper evidence on the resulting artifacts

Windows remains pending:

- select and integrate a trusted Authenticode route suitable for direct GitHub ZIP distribution
- keep signing authority/private-key material in compliant hardware/cloud protection or an approved signing service
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

PR #24 established durable project context, PR #25 split the desktop release workflows, and PR #26 added the cheap legal-material preflight. The current controlled PR implements the macOS production signing/notarization path without running an expensive credential-backed package build yet. Windows signing, forward-compatibility and UI modernization remain separate follow-up work.
