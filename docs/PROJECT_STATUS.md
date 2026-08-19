# Project Status

Last updated: 2026-08-19

## Published release

- Version: `v1.3.0`
- Release commit: `fb2193dfc13d0f0e6b7be660c1342bbf87d26081`
- State: published, latest until v1.4.0 is published
- Release history/assets: immutable
- Public assets: exactly 8
- Prebuilt platforms: Windows x64/ARM64, Linux x64/ARM64, macOS x64/ARM64

v1.3.0 must not be rebuilt, retagged, rewritten or have its published binary assets replaced.

## v1.4 release target

The repository is being prepared for `v1.4.0` as a public Windows engineering/test release.

- Canonical application version on `main`: `1.4.0`
- Prebuilt v1.4 platforms: Windows x64 + Windows ARM64 only
- Signing: intentionally unsigned for v1.4
- Linux/macOS: source support retained; no new v1.4 package builds
- Production signing and the full six-platform production release are deferred to v1.5
- v1.4 public asset model: exactly 4 files
  - Windows x64 ZIP
  - Windows ARM64 ZIP
  - consolidated third-party source `tar.xz`
  - `SHA256SUMS.txt`

The v1.4 engineering release still uses one frozen exact `main` SHA, strict package/legal validation, native architecture checks, packaged smoke tests, consolidated corresponding-source validation and release-wide checksums.

No v1.4 Nuitka release-candidate build has been dispatched yet. Do not freeze the final v1.4 SHA until the remaining UI cleanup is merged and post-merge Quality/UI audit passes.

## Current baselines

- Packaging Python: 3.13
- Quality Python: 3.13 + 3.14
- `PySide6-Essentials`: 6.11.1
- Nuitka: 4.1.3
- UI technology: Qt Widgets
- Production application style: Qt platform/default QStyle; no production/global forced Fusion
- Windows v1.4 release signing: unsigned by deliberate policy
- Windows v1.5 production path: Microsoft Artifact Signing Public Trust + SHA-256/RFC3161 + native x64/ARM64 post-sign verification implemented; real Azure credential/profile-backed validation deferred to v1.5
- macOS v1.5 production path: Developer ID + hardened runtime + secure timestamp + notarization/stapling/Gatekeeper implemented; real credential-backed validation deferred to v1.5

## Current workflows

- `.github/workflows/quality.yml`
- `.github/workflows/ui-style-audit.yml`
- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/assemble-windows-engineering-release.yml`
- `.github/workflows/sign-windows.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`
- `.github/workflows/assemble-release.yml`

Profile usage:

- v1.4: `build-windows-exe.yml` with `target=both`, then `assemble-windows-engineering-release.yml`
- v1.5 production target: Windows build + Windows signing + Linux build + macOS production build, then `assemble-release.yml`

The UI style audit is source/render validation only and never builds release packages.

## Current release and audit scripts

- `.github/scripts/assemble_release_assets.py`
- `.github/scripts/assemble_windows_engineering_release.py`
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

## Durable release invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits.
- Published release history is immutable.
- Every release profile derives all of its artifacts from one exact frozen SHA.
- No public RC tag and no tag-triggered binary rebuild.
- Strict legal/source validation remains mandatory.
- Managed ADB remains read-only with respect to installed Android apps.
- If source or release tooling changes after a release SHA is frozen, discard and rebuild all candidates required by that selected release profile from the new SHA.

See `PROJECT_DECISIONS.md` and `BUILDING.md` for rationale and exact procedures.

## v1.4 progress

### Durable context and release architecture

Completed:

- PR #24: refreshed durable project context and release documentation
- PR #25: split Linux and macOS release workflows
- PR #26: added pre-Nuitka legal-material preflight
- PR #27: implemented macOS Developer ID/notarization production path
- PR #28: implemented Windows Microsoft Artifact Signing production path
- PR #29: added proactive forward-compatibility regression guard
- PR #30: added cross-platform Qt native-style audit
- PR #31: adopted Qt platform/default production style
- PR #32: removed shared hard-coded font/scrollbar QSS and several stale developer Fusion overrides
- PR #33: bumped the canonical version to 1.4.0, added the Windows-only engineering release assembler/workflow and aligned durable/public documentation to the v1.4 engineering and v1.5 production profiles

PR #33 merged to `main` as `9262164ab08a8c8602ebbea03a615e0d950692a1` after Quality passed on Python 3.13 and 3.14.

### v1.4 Windows engineering release preparation

Merged in PR #33:

- canonical application version `1.4.0`
- a dedicated Windows-only engineering assembler
- a manual exact-SHA `Assemble Windows engineering release` workflow
- exact four-asset validation
- tests for the Windows engineering profile
- Quality compilation/lint coverage for the new assembler helper
- README, changelog and durable release documentation aligned to v1.4 Windows-only unsigned publication and v1.5 signing

The full six-platform production assembler and both signing implementations remain intact for v1.5.

### Final UI modernization cleanup before v1.4 freeze

Active branch: `agent/v1.4-finish-native-style-cleanup`.

Five developer-only standalone launchers still contain exactly one stale `app.setStyle("Fusion")` line each:

- `playstore_app_audit/ui/audit_window.py`
- `playstore_app_audit/ui/compact_window.py`
- `playstore_app_audit/ui/device_window.py`
- `playstore_app_audit/ui/insights_window.py`
- `playstore_app_audit/ui/preferences_window.py`

They do not affect canonical production startup. The cleanup branch has already replaced the temporary allowlist regression test with a repository-wide assertion that first-party package code contains no `.setStyle(...)` call. The five identical developer-only lines are the only remaining code edits before that test can pass.

After the five lines are removed, run normal Quality plus the cross-platform UI style audit, merge the branch normally, update this status to mark the cleanup complete, and only then freeze the v1.4 release SHA.

### GitHub Actions / Node

The application itself does not use Node. Monitor official action majors for future Node 26 runtime adoption and upgrade only when official actions support/adopt it. Do not add `setup-node` merely to force Node 26.

A daily conditional monitor has been created outside the repository to surface meaningful official Node 26 action-major changes without changing source control.

### Signing work deferred to v1.5

Do not run real Windows Artifact Signing or macOS Developer ID/notarization for v1.4.

For v1.5, credential-backed validation still requires:

Windows:

- eligible Microsoft Artifact Signing account and Public Trust certificate profile
- GitHub OIDC/federated Azure identity with the required signing role
- secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- repository variables: `WINDOWS_ARTIFACT_SIGNING_ENDPOINT`, `WINDOWS_ARTIFACT_SIGNING_ACCOUNT_NAME`, `WINDOWS_ARTIFACT_SIGNING_CERTIFICATE_PROFILE_NAME`

macOS:

- Apple Developer membership and Developer ID Application certificate
- App Store Connect notary API credentials
- secrets: `MACOS_DEVELOPER_ID_APPLICATION_P12_BASE64`, `MACOS_DEVELOPER_ID_APPLICATION_P12_PASSWORD`, `MACOS_DEVELOPER_ID_TEAM_ID`, `MACOS_NOTARY_API_KEY_P8_BASE64`, `MACOS_NOTARY_KEY_ID`, `MACOS_NOTARY_ISSUER_ID`

## v1.4 remaining sequence

Before any heavy build:

1. remove the five developer-only Fusion lines on `agent/v1.4-finish-native-style-cleanup`;
2. run/merge that cleanup with Quality on Python 3.13/3.14 and the cross-platform UI style audit green;
3. refresh `PROJECT_STATUS.md` to record the merged cleanup and confirm README/changelog/version/durable docs still describe the intended v1.4 Windows engineering profile;
4. freeze the exact final `main` SHA only after the above is complete.

Then:

5. manually dispatch `Build Windows - Qt6` from that exact SHA with `target=both`;
6. require both x64 and ARM64 jobs and their package/legal/smoke validations to pass;
7. dispatch `Assemble Windows engineering release` from the same SHA using that successful Windows run ID;
8. require exactly four validated final assets;
9. manually verify the final checksum manifest and, if desired, smoke-test the downloaded Windows packages;
10. create the annotated `v1.4.0` tag on the frozen SHA;
11. publish the already validated four assets without rebuilding, clearly labeling them Windows-only and unsigned;
12. treat the published v1.4.0 tag/assets as immutable.

## Housekeeping that does not block v1.4

- Edit older published GitHub Release descriptions where maintainer-only pipeline notes remain when release-write capability is available.
- Delete merged short-lived remote branches when a safe branch-delete capability or authenticated local shell is available.

Neither housekeeping item justifies changing published v1.3.0 binaries or delaying the v1.4 Windows engineering release.

## Known release lessons

- Catch deterministic legal/source failures before expensive compilation where possible.
- Compiler success alone is not release evidence; package, architecture, startup, legal and provenance validation remain mandatory.
- Never mix release artifacts from different source SHAs.
- Platform workflow isolation must not weaken release source identity.
- A reduced-cost engineering release must have its own explicit asset/profile validator rather than weakening the full production assembler.
