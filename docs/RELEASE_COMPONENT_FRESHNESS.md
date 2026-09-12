# Release component freshness gate

This is a mandatory release invariant for Play Store App Audit. It applies to every release, including patch releases.

## Two mandatory gates

Run the complete component freshness audit twice:

1. **Release-phase entry gate** - before release-specific stabilization, version freeze or packaging starts.
2. **Final pre-release gate** - after the final product changes are complete and immediately before the exact release SHA is frozen for production builds/publication.

A release may not pass either gate with a known newer stable component left unapplied. If a newer stable upstream version exists, update the component and repeat every affected source, quality, packaging, legal, signing and platform validation before release work continues.

Pre-releases, release candidates, betas, alphas, nightlies and development snapshots do not count as the latest stable version. They are evaluated separately and are adopted only through an explicit engineering decision.

## Audit scope

The audit covers the complete maintained release toolchain, not only application runtime dependencies:

- Python release runtime and supported Python baseline.
- Direct Python runtime dependencies from `requirements.txt` and `pyproject.toml`.
- Development/test dependencies from `requirements-dev.txt`.
- Transitive Python packages resolved in a clean environment; inspect `python -m pip list --outdated` after installing the pinned dependency set and investigate every result that is part of the release/runtime/tooling path.
- Qt/PySide and Shiboken supplied by the selected PySide release.
- Nuitka and any deployment/compiler tooling used by the packaged builds.
- setuptools, wheel, pip and other packaging/build-system components used by the release process.
- GitHub Actions used by every maintained workflow, including checkout, Python setup, artifact upload/download and signing/login actions.
- Android Platform-Tools / ADB used by the managed-download path. If the application intentionally uses an upstream `*-latest-*` endpoint, verify that the endpoint still resolves to the current stable Platform-Tools release and that the managed archive validation remains valid.
- Windows signing tooling/provider actions and macOS signing/notarization tooling used by the production release path.
- OS/runner images and architecture-specific build prerequisites where the project pins or deliberately selects a maintained version.
- Any other third-party runtime, binary, library, action or release utility shipped with, downloaded by, or required to build/validate the release.

Historical release documents and immutable published release artifacts are evidence of their original release and are not rewritten merely because the current toolchain advances.

## Required evidence

For each gate, record in the active release checklist or handoff:

- audit date;
- component/tool name;
- version selected by the repository;
- latest stable upstream version found;
- authoritative upstream source used to verify it;
- action taken (`current`, `updated`, or explicit release-blocking issue while an update is being validated);
- validation repeated after any update.

The final pre-release record must refer to the exact dependency/workflow state that will be frozen for production builds.

## Update and validation rule

When an update is required, treat it as release work rather than a documentation-only change. At minimum:

1. update the canonical pin/configuration and every duplicated runtime/build reference;
2. update current/future-facing documentation without rewriting historical release facts;
3. run source Quality on the supported Python baseline;
4. run the affected native/package smoke, architecture, legal/source and signing/notarization checks;
5. discard stale release candidates produced before the toolchain change;
6. repeat this freshness gate until every maintained component is confirmed current against the latest stable upstream release.

If an upstream stable release cannot be adopted because it is incompatible or defective, the release is blocked until the incompatibility is resolved or a deliberate engineering decision changes this invariant. Do not silently ship an older known-stable component under this policy.
