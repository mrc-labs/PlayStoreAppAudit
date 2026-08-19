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
- Windows v1.4 production path: Microsoft Artifact Signing Public Trust + SHA-256/RFC3161 + native x64/ARM64 post-sign verification implemented in workflow code; real Azure credential/profile-backed production validation still pending

## Current workflows

- `.github/workflows/quality.yml`
- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/sign-windows.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`
- `.github/workflows/assemble-release.yml`

The production release-candidate model is:

- Windows native build workflow: x64 + ARM64 unsigned intermediate packages from the frozen SHA
- Windows signing workflow: accepts only a successful exact-SHA native Windows build, signs both owned primary executables, reruns strict legal checks and natively verifies both final packages
- Linux workflow: x64 + ARM64
- macOS workflow: x64 + ARM64 production signing/notarization mode
- assembler: accepts the signed Windows run plus distinct Linux/macOS run IDs, validates all six final candidates and emits exactly eight public files

All package/signing workflows remain deliberate manual release operations and exact-SHA guarded. The assembler must not accept an unsigned Windows build run as its Windows release source.

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

Repository documentation/context cleanup was completed in PR #24.

Completed repository work:

- refreshed `AGENTS.md`
- added `PROJECT_DECISIONS.md` and `PROJECT_STATUS.md`
- corrected README six-platform v1.3.0 distribution text
- corrected `BUILDING.md` and `ARCHITECTURE.md` release model
- cleaned CHANGELOG maintainer-only process details

Still open outside repository-content changes:

- audit/edit published GitHub Release descriptions where maintainer-only pipeline notes remain, once a release-write connector/action is available
- delete merged short-lived remote branches when branch-delete capability is available

Neither housekeeping item justifies changing v1.3.0 binaries, tags or release history.

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

macOS workflow implementation was merged in PR #27:

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

Windows workflow implementation was merged in PR #28:

- native x64 + ARM64 build remains in `build-windows-exe.yml`
- a separate `sign-windows.yml` accepts only the successful exact-SHA unsigned Windows build
- Microsoft Artifact Signing Public Trust through GitHub OIDC
- only the owned top-level `PlayStoreAppAudit.exe` is signed
- SHA-256 file digest and RFC3161 timestamp are required
- non-target package hashes must remain unchanged
- legal runtime evidence is refreshed and strict public legal validation reruns after signing
- final signed x64 and ARM64 packages are re-extracted, signature-verified and smoke-tested on native Windows runners
- the release assembler accepts only the successful signed-Windows run, not the unsigned build run

Still required before calling production Windows signing validated:

- provision an eligible Artifact Signing account, completed identity validation and production Public Trust certificate profile
- configure GitHub OIDC/federated Azure identity and the documented secrets/repository variables
- grant the Azure identity the required signing role on the Artifact Signing resources
- run one deliberate production Windows native build + signing workflow for both architectures
- confirm public-trust Authenticode, timestamp and native x64/ARM64 package evidence

### P2 - Forward compatibility

The proactive v1.4 sweep is covered by PR #29.

Audit result:

- no first-party migration candidate was found that met the policy of documented deprecation/supersession plus behaviour-equivalent replacement;
- the custom `QSortFilterProxyModel` already uses `beginFilterChange()` / `endFilterChange()` rather than the invalidation APIs scheduled for deprecation;
- no deprecated `QCheckBox.stateChanged(int)` connections were found;
- no obsolete Qt mouse-position accessors or legacy PySide `exec_` calls were found;
- no Python `datetime.utcnow()` / `utcfromtimestamp()`, `locale.getdefaultlocale()` or `logging.warn()` calls were found;
- no imports of the Python 3.13-removed legacy standard-library modules checked by the sweep were found.

PR #29 adds a curated first-party regression sentinel for the deprecated/superseded APIs reviewed in this sweep. It is intentionally not an exhaustive static deprecation detector and should be extended only with primary documentation evidence.

Python 3.14 remains a Quality compatibility target; production packaging remains on Python 3.13 until a deliberate toolchain migration.

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

PR #24 established durable project context, PR #25 split the desktop release workflows, PR #26 added the cheap legal-material preflight, PR #27 implemented the macOS production signing/notarization path, PR #28 implemented the Windows production signing path and PR #29 records the proactive forward-compatibility sweep with regression sentinels. Credential-backed production validation for both signing platforms remains deliberate release work. Node-runtime monitoring and UI modernization remain separate follow-up workstreams.
