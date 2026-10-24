# Release component freshness gate

This is a mandatory release invariant for Store App Audit. It applies to every release, including patch releases.

## Permanent latest-stable selection rule (reaffirmed 2026-10-24)

This is a standing project rule for **every component and every release**, not an OpenSSL-only exception. Select the **latest stable compatible version** across runtime, direct/transitive dependencies, embedded native libraries, build/deployment tools, CI Actions and their relevant internals, SDKs, managed downloads, and release/legal/assembly tooling. Recheck announced deprecations, removals, support ends and applicable advisories before selection and before freeze.

- LTS longevity, an existing pin, a working old integration, a vendor snapshot, or inclusion inside a current parent is **not by itself a reason to retain an older version** when a newer stable supported compatible integration is available.
- The A/B/C/D categories below identify ownership and the safe upgrade path; they do not exempt nested components from inventory, version comparison or support/security review.
- For an older nested component, check newer parent releases, supported parent configuration, supported vendor alternatives and a controlled rebuild where appropriate. Record the actual integration/target constraint if the newer release cannot be used. Do not label a selected parent “current” as a substitute for evaluating its internals.
- Proactively migrate concretely announced deprecations/EOLs when a stable supported compatible successor exists. Shipping just before a known support end is not a substitute for evaluating and applying that migration now.
- Preview software, experimental integration, unsupported ABI/DLL substitution, weakened verification and implicit removal of an architecture or compatibility floor are not acceptable ways to claim freshness. An incompatible newest version requires explicit evidence and a supported alternative or a release blocker; convenience and validation cost are not compatibility evidence.
- Preserve the versioning rule below. If the required refresh needs a source fix or compatibility adaptation, reassess the MINOR release classification; do not omit an otherwise required update merely to preserve a PATCH number.
- This governs software built/distributed by the project and its relevant build environment. It does not authorize arbitrary upgrades of a maintainer's unrelated OS applications, other projects or local Docker/DDEV resources. Published source/tag/assets remain immutable.

## Monthly first-day freshness cycle

The complete component-freshness process is also a permanent monthly maintenance gate.

- Run it on the first day of every month, not only immediately before a feature release.
- Inventory every directly used runtime, dependency, GitHub Action, compiler/deployment tool, Android Platform-Tools path, native platform prerequisite, legal/source helper and release/assembly component.
- Recheck current stable versions plus announced deprecations, removals, EOL/support dates and applicable security/support changes from authoritative upstream sources.
- Adopt a newer stable compatible component through a supported integration when available, including the evaluated embedded/transitive paths below, unless a concrete target-compatibility blocker is recorded and kept under watch.
- A pure component/toolchain refresh with no application/source change is a PATCH release. Any source fix or compatibility adaptation required by the refresh is a MINOR release with PATCH reset to zero.
- Record explicit no-action and future-watch decisions so a component is never treated as current merely because no repository pin changed.
- Every resulting release still follows the normal exact-SHA validation, build, assembly, publication and closure gates.

## Two mandatory gates

Run the complete component freshness audit twice:

1. **Release-phase entry gate** - before release-specific stabilization, version freeze or packaging starts.
2. **Final pre-release gate** - after the final product changes are complete and immediately before the exact release SHA is frozen for production builds/publication.

A release may not pass either gate with a known newer stable compatible component under repository control left unapplied. Compatibility is evaluated against the complete maintained support matrix, including architecture and binary compatibility requirements. Apply the ownership categories below to establish the supported upgrade path. Evaluate every newer embedded/transitive version; a current supported parent is not an automatic freshness exemption.

Pre-releases, release candidates, betas, alphas, nightlies and development snapshots do not count as the latest stable version. They are evaluated separately and are adopted only through an explicit engineering decision.

## Ownership and compatibility decision (2026-10-01)

This is an explicit release-engineering decision, not an individual waiver. All six maintained targets remain required.

### A. Directly selected or pinned components

Use the **latest stable compatible release** for the maintained support matrix. This covers direct runtime/dev dependencies, independently resolved transitive packages, Nuitka, directly referenced Actions, the Python runtime and independently selected tools. A newer compatible release under repository control must be adopted and validated. A compatibility exception must identify the affected target, concrete incompatibility, authoritative evidence and maintained selected alternative. Preference, convenience or validation cost is not an exception.

### B. Upstream-bundled components

Inventory the **actual embedded versions per relevant target** as well as the parent: for example official CPython with OpenSSL/Expat/compression libraries, matched PySide/Shiboken/Qt wheels and TLS providers, or a compiler/runtime bundle. Compare these with current stable upstream versions and support/security facts. A current supported parent alone does not discharge this check.

When a newer embedded component exists, evaluate a newer supported parent, a supported configuration/vendor integration or a controlled rebuild that preserves the maintained target matrix and compatibility floors. Use the latest stable compatible integration available. Do not retain an older family merely because it is LTS or shipped by the parent. If no supported compatible route exists, record the target-specific technical evidence, selected supported alternative, remaining advisory/support risk and the maintained watch or release blocker. Unsupported parents, applicable unresolved security findings and unresolved required upgrades remain blockers.

Do not replace linked DLLs/SONAMEs mechanically or assume that an independently newer major is ABI compatible. A custom parent rebuild or compatibility adaptation must be scoped, validated and classified under the release versioning policy. Independently selected components are category A; embedding them does not erase repository ownership.

### C. Vendor-owned implementation internals

Use the latest stable supported parent Action/integration and inspect its relevant internal packages and nested Actions. Record version gaps, support/deprecation dates and advisory applicability; do not assume that vendor ownership makes an old internal component acceptable.

Check for a newer supported parent, a supported override/configuration or a supported alternative integration. Adopt an available stable compatible route and validate it. When the repository cannot safely control the internal selection, record the exact ownership boundary and incompatibility/support evidence, then classify the result as an explicit upstream watch or blocker under the permanent rule. A vendor fork is not an automatic requirement, but neither is “vendor internal” an automatic exemption. Reopen the decision when parent, support, advisory or supported-alternative facts change.

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
- ownership category, actual provider/parent and repository control boundary;
- version selected by the repository;
- latest stable upstream version and latest compatible supported selection, if different;
- authoritative upstream source used to verify it;
- compatibility/support/advisory evidence for any differing selection or upstream observation, including which supported upgrade paths were checked and why an older embedded/provider version remains selected;
- action taken (`current`, `updated`, `supported parent/upstream observation`, or an explicit release blocker);
- validation repeated after any update.

The final pre-release record must refer to the exact dependency/workflow state that will be frozen for production builds.

## Aggregated release benefit report

Every release, including a maintenance-only PATCH, must include a **concise aggregated benefit report** for the maintainer alongside the detailed component inventory. Group the report by practical outcomes, not one paragraph or row per upgraded dependency. Record it in the active release issue or an existing genuine release audit/preparation record; do not create a standalone handoff/status/command-carrier document merely to hold this summary.

- Compare the selected release state with the **previous published release**, not an intermediate PR or diagnostic build. Exclude fixes already present in that baseline and unreleased changes not selected for the new packages.
- Summarize relevant security/trust fixes, stability/correctness improvements, supported-platform/deprecation migrations, and performance/resource changes **only when supported by evidence**. Omit empty categories; a reasonable default is 3–6 outcome bullets.
- Explain serious applicable fixes in plain language: the failure or attack addressed, its affected scope, the upstream severity/advisory reference and whether the affected path is present/reachable in this application. Distinguish an affected bundled library from demonstrated application exposure. Never promote a low-severity or non-applicable upstream issue to a critical application vulnerability.
- Distinguish **measured in this project**, **documented upstream but not measured here**, and **not applicable / still pending**. Do not invent speed, memory, startup or reliability gains from a version bump or passing tests. Benchmark only when a performance claim needs it.
- Separate improvements to the distributed application from improvements confined to developer tools/CI. Include material compatibility changes, regressions, unresolved support/security findings or limitations rather than presenting only positive effects.
- Link the aggregate conclusions to authoritative release notes/advisories and the relevant project validation, while leaving the component-by-component detail in the audit matrix.
- Produce a preliminary report after the entry audit/refresh. Reconcile the final report with the **actual frozen SHA, selected dependency versions and six accepted package inventories** before release acceptance. A successful source test or one native diagnostic does not establish benefit/verification on all targets.

This report does not change the standard four-section public Release body. Maintenance-only public highlights remain the established short sentence unless a material user-impacting security/compatibility fact needs disclosure; the fuller maintainer report stays linked in the release ledger/audit. Full closure must retain the final aggregate report and its evidence.

## Update and validation rule

When an update is required, treat it as release work rather than a documentation-only change. At minimum:

1. update the canonical pin/configuration and every duplicated runtime/build reference;
2. update current/future-facing documentation without rewriting historical release facts;
3. run source Quality on the supported Python baseline;
4. run the affected native/package smoke, architecture, legal/source and signing/notarization checks;
5. discard stale release candidates produced before the toolchain change;
6. repeat this freshness gate until every maintained component satisfies its ownership/compatibility category and all required validation passes.

If a newer compatible directly controlled stable release cannot be adopted or validated, the release is blocked until the problem is resolved. A newer incompatible baseline may instead be recorded with the concrete target-matrix evidence and supported alternative required above. Do not silently waive an update, an applicable security/support finding, native/source/legal validation, or a maintained release target.
