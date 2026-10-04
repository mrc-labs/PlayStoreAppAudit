# Release component freshness gate

This is a mandatory release invariant for Store App Audit. It applies to every release, including patch releases.

## Monthly first-day freshness cycle

The complete component-freshness process is also a permanent monthly maintenance gate.

- Run it on the first day of every month, not only immediately before a feature release.
- Inventory every directly used runtime, dependency, GitHub Action, compiler/deployment tool, Android Platform-Tools path, native platform prerequisite, legal/source helper and release/assembly component.
- Recheck current stable versions plus announced deprecations, removals, EOL/support dates and applicable security/support changes from authoritative upstream sources.
- Adopt a newer stable compatible directly selected component when available, unless a concrete target-compatibility blocker is recorded and kept under watch.
- A pure component/toolchain refresh with no application/source change is a PATCH release. Any source fix or compatibility adaptation required by the refresh is a MINOR release with PATCH reset to zero.
- Record explicit no-action and future-watch decisions so a component is never treated as current merely because no repository pin changed.
- Every resulting release still follows the normal exact-SHA validation, build, assembly, publication and closure gates.

## Two mandatory gates

Run the complete component freshness audit twice:

1. **Release-phase entry gate** - before release-specific stabilization, version freeze or packaging starts.
2. **Final pre-release gate** - after the final product changes are complete and immediately before the exact release SHA is frozen for production builds/publication.

A release may not pass either gate with a known newer stable compatible component under repository control left unapplied. Compatibility is evaluated against the complete maintained support matrix, including architecture and binary compatibility requirements. Apply the ownership categories below; a globally newer version alone does not make a supported vendor bundle stale.

Pre-releases, release candidates, betas, alphas, nightlies and development snapshots do not count as the latest stable version. They are evaluated separately and are adopted only through an explicit engineering decision.

## Ownership and compatibility decision (2026-10-01)

This is an explicit release-engineering decision, not an individual waiver. All six maintained targets remain required.

### A. Directly selected or pinned components

Use the **latest stable compatible release** for the maintained support matrix. This covers direct runtime/dev dependencies, independently resolved transitive packages, Nuitka, directly referenced Actions, the Python runtime and independently selected tools. A newer compatible release under repository control must be adopted and validated. A compatibility exception must identify the affected target, concrete incompatibility, authoritative evidence and maintained selected alternative. Preference, convenience or validation cost is not an exception.

### B. Upstream-bundled components

Evaluate freshness at the **supported upstream parent package/runtime boundary**: for example official CPython with its OpenSSL, the matched PySide/Shiboken/Qt wheel set, or a supported vendor compiler/runtime bundle. Record the actual embedded version. Do not replace an embedded library merely to match a newer independent major. It becomes a blocker if the parent is stale, an applicable security advisory requires action, the repository deliberately overrides it, or upstream declares it unsupported. Independently provisioned libraries remain subject to category A within their supported integration; they cannot be relabelled bundled merely to avoid an available compatible update.

### C. Vendor-owned implementation internals

Use the latest stable supported parent Action/integration. Record older internal packages and nested Actions as upstream observations/risks when they are not exposed as repository configuration. They become blockers when the repository can safely select/override them, a newer supported parent release updates them, an applicable security/trust issue requires action, or the integration is demonstrably broken/unsupported. Do not fork a vendor Action solely to satisfy a mechanical latest-version comparison.

### D. OS, runner and compiler toolchains

Use a current supported toolchain compatible with every maintained release target and the intended binary compatibility floor. Record the selected supported baseline, newer incompatible option, incompatibility evidence and continued maintenance of the selected baseline. A globally newer toolchain that drops a required architecture is not automatically mandatory. A newer compatible baseline that preserves the required targets and compatibility floor still requires adoption and validation. Do not retain unsupported runners or raise the product compatibility floor implicitly.

Security/support findings must be evaluated for applicability; absence of a version gap is not proof of security. An observation must be reopened when its parent/support/advisory facts change. Unsupported parents, actionable advisories, unresolved required upgrades and missing validation remain real gate blockers.

## Development tracking and final Python patch freeze

During development, `3.14` with `check-latest: true` may track the latest stable patch. The gate must compare python.org with setup-python's published builds and inspect the **actual full runtime version** used by each validation job. A current upstream patch missing from the hosted manifest is a propagation blocker when hosted evidence is required; do not invent a custom distribution just to bypass normal propagation.

At the final pre-release gate, resolve the exact current compatible stable Python patch. **Before freezing the release SHA**, replace the development version selectors in the maintained release-producing workflows with that same literal `major.minor.patch`, disable rolling latest checks for those exact pins, and make their runtime checks fail closed on `platform.python_version()` equality. Apply the same exact patch to final Quality and any signing/assembly jobs that install Python. Review all duplicated selectors/assertions together and rerun affected validation before freezing the SHA. All six final candidates must use that approved patch unless a platform-specific upstream distribution limitation is explicitly documented and accepted.

The chosen mechanism is ordinary full-version YAML literals plus exact runtime assertions in the existing workflows, not a new toolchain configuration system. This entry gate does not populate or freeze those final patch pins. Record actual Python/tool versions in package provenance. Recheck freshness immediately before freeze; if the selected patch changes afterwards, invalidate and rebuild the required candidate set from a new exact SHA.

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
- ownership category and repository control boundary;
- version selected by the repository;
- latest stable upstream version and latest compatible supported selection, if different;
- authoritative upstream source used to verify it;
- compatibility/support/advisory evidence for any differing selection or upstream observation;
- action taken (`current`, `updated`, `supported parent/upstream observation`, or an explicit release blocker);
- validation repeated after any update.

The final pre-release record must refer to the exact dependency/workflow state that will be frozen for production builds.

## Update and validation rule

When an update is required, treat it as release work rather than a documentation-only change. At minimum:

1. update the canonical pin/configuration and every duplicated runtime/build reference;
2. update current/future-facing documentation without rewriting historical release facts;
3. run source Quality on the supported Python baseline;
4. run the affected native/package smoke, architecture, legal/source and signing/notarization checks;
5. discard stale release candidates produced before the toolchain change;
6. repeat this freshness gate until every maintained component satisfies its ownership/compatibility category and all required validation passes.

If a newer compatible directly controlled stable release cannot be adopted or validated, the release is blocked until the problem is resolved. A newer incompatible baseline may instead be recorded with the concrete target-matrix evidence and supported alternative required above. Do not silently waive an update, an applicable security/support finding, native/source/legal validation, or a maintained release target.
