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

The repository is being prepared for `v1.4.0` as a public Windows x64 engineering/test release.

- Canonical application version on `main`: `1.4.0`
- Prebuilt v1.4 platform: Windows x64 only
- Signing: intentionally unsigned for v1.4
- Windows ARM64/Linux/macOS: source support retained; no new v1.4 package builds
- Production signing and the full six-platform production release are deferred to v1.5
- v1.4 public asset model: exactly 3 files
  - Windows x64 ZIP
  - consolidated third-party source `tar.xz`
  - `SHA256SUMS.txt`

The v1.4 engineering release still uses one frozen exact `main` SHA, strict package/legal validation, native x64 architecture checks, packaged smoke tests, corresponding-source validation and release-wide checksums.

No v1.4 Nuitka release-candidate build has been dispatched yet. Do not freeze the final v1.4 SHA until PR #34 is merged and its post-merge Quality/UI validation passes.

## Current baselines

- Packaging Python: 3.13
- Quality Python: 3.13 + 3.14
- `PySide6-Essentials`: 6.11.1
- Nuitka: 4.1.3
- UI technology: Qt Widgets
- Production application style: Qt platform/default QStyle; no production/global forced Fusion
- Windows v1.4 release signing: unsigned by deliberate policy
- Windows v1.5 production signing: Microsoft Artifact Signing Public Trust implementation exists with SHA-256/RFC3161 and native x64/ARM64 post-sign verification, but the final public-trust provider is not locked until v1.5. Revalidate publisher eligibility and cost before execution and adapt the signing stage if another trusted provider is required.
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

- v1.4: `build-windows-exe.yml` with `target=x64`, then `assemble-windows-engineering-release.yml`
- v1.5 production target: Windows build + validated public-trust Windows signing + Linux build + macOS production build, then `assemble-release.yml`

The v1.4 engineering assembler requires the x64 artifact and rejects a source run that also contains the canonical Windows ARM64 artifact.

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
- PR #33: bumped the canonical version to 1.4.0, added the Windows engineering release assembler/workflow and aligned durable/public documentation to the v1.4 engineering and v1.5 production profiles

PR #33 merged to `main` as `9262164ab08a8c8602ebbea03a615e0d950692a1` after Quality passed on Python 3.13 and 3.14.

After PR #33, the intended v1.4 engineering target was corrected from Windows x64+ARM64 to Windows x64 only before any release build was dispatched. PR #34 carries that correction through the assembler, workflow, tests and durable/public documentation.

### v1.4 Windows x64 engineering release preparation

PR #34 corrects the PR #33 engineering profile to:

- canonical application version `1.4.0`
- Windows x64 only
- unsigned engineering/test publication
- a dedicated x64-only engineering assembler
- a manual exact-SHA `Assemble Windows engineering release` workflow
- exact three-asset validation
- rejection of Windows ARM64 input for the v1.4 engineering assembler
- README, changelog and durable release documentation aligned to x64-only v1.4 publication and v1.5 signing/full production

The full six-platform production assembler and both signing implementations remain intact for v1.5.

### Final UI modernization cleanup before v1.4 freeze

PR #34: `release: finalize v1.4 x64 engineering profile`.

The five remaining developer-only `app.setStyle("Fusion")` overrides were removed in commit `fd6668c9c70104554d998cec9d975e21caf18c80` from:

- `playstore_app_audit/ui/audit_window.py`
- `playstore_app_audit/ui/compact_window.py`
- `playstore_app_audit/ui/device_window.py`
- `playstore_app_audit/ui/insights_window.py`
- `playstore_app_audit/ui/preferences_window.py`

Each UI module changed by exactly one deletion and no additions. The cleanup branch also replaces the temporary allowlist regression test with a repository-wide assertion that first-party package code contains no `.setStyle(...)` call.

Local targeted validation on Python 3.14.6 passed `tests/test_app_style_policy.py` and `tests/test_windows_engineering_release.py` with 5 tests passing. PR #34 Quality and cross-platform UI style audit are the remaining pre-merge gates. After PR #34 merges normally and post-merge validation is green, refresh this status once more and freeze the v1.4 release SHA.

### GitHub Actions / Node

The application itself does not use Node. Monitor official action majors for future Node 26 runtime adoption and upgrade only when official actions support/adopt it. Do not add `setup-node` merely to force Node 26.

A daily conditional monitor has been created outside the repository to surface meaningful official Node 26 action-major changes without changing source control.

### Signing work deferred to v1.5

Do not run real Windows public-trust signing or macOS Developer ID/notarization for v1.4.

Windows:

- the repository currently implements Microsoft Artifact Signing Public Trust through `.github/workflows/sign-windows.yml`
- do not assume Microsoft is the final v1.5 provider until publisher eligibility and cost are revalidated at the v1.5 signing milestone
- if Microsoft remains usable, the existing OIDC path requires `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` plus `WINDOWS_ARTIFACT_SIGNING_ENDPOINT`, `WINDOWS_ARTIFACT_SIGNING_ACCOUNT_NAME`, and `WINDOWS_ARTIFACT_SIGNING_CERTIFICATE_PROFILE_NAME`
- if another publicly trusted code-signing provider is chosen, adapt or replace the signing stage while retaining exact-SHA provenance, signature/timestamp verification, native x64/ARM64 post-sign verification, legal revalidation and fail-closed assembly

macOS:

- Apple Developer membership and Developer ID Application certificate
- App Store Connect notary API credentials
- secrets: `MACOS_DEVELOPER_ID_APPLICATION_P12_BASE64`, `MACOS_DEVELOPER_ID_APPLICATION_P12_PASSWORD`, `MACOS_DEVELOPER_ID_TEAM_ID`, `MACOS_NOTARY_API_KEY_P8_BASE64`, `MACOS_NOTARY_KEY_ID`, `MACOS_NOTARY_ISSUER_ID`

## v1.4 remaining sequence

Before any heavy build:

1. PR #34 must pass Quality on Python 3.13/3.14 and the cross-platform UI style audit;
2. merge PR #34 with a normal merge commit;
3. require post-merge Quality/UI validation on `main` to remain green;
4. refresh `PROJECT_STATUS.md` to record the merged cleanup and confirm README/changelog/version/durable docs still describe the intended v1.4 Windows x64 engineering profile;
5. freeze the exact final `main` SHA only after the above is complete.

Then:

6. manually dispatch `Build Windows - Qt6` from that exact SHA with `target=x64`;
7. require the x64 package/legal/smoke validation job to pass;
8. dispatch `Assemble Windows engineering release` from the same SHA using that successful Windows x64 run ID;
9. require exactly three validated final assets;
10. manually verify the final checksum manifest and, if desired, smoke-test the downloaded Windows x64 package;
11. create the annotated `v1.4.0` tag on the frozen SHA;
12. publish the already validated three assets without rebuilding, clearly labeling the binary as Windows x64 only and unsigned;
13. treat the published v1.4.0 tag/assets as immutable.

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
