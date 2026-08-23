from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, *, path: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:100]!r}")
    return text.replace(old, new, 1)


RELEASE_SHA = "e2d09098bc42c6f16d202d010deda3eb24d99aa3"
WINDOWS_SHA = "142b15e40fba3d7ed8b29e1e37b366551dde3cf65e18608434869f4528d50c1b"
SOURCES_SHA = "9a3991509a8629a2827074b939975c048695b4557e2e22635eef35336c682458"
SUMS_SHA = "984d81cc77f60e10b1033199ba71b4737adb0b272c416d268a8e5025226e2ae9"

# AGENTS.md
path = "AGENTS.md"
text = read(path)
text = replace_once(
    text,
    "The full checklist and rationale are canonical in `docs/RELEASE_CLOSURE.md` and apply to v1.7, v1.8, v2.0 and every later release line.",
    "The full checklist and rationale are canonical in `docs/RELEASE_CLOSURE.md` and apply to v1.7, v1.8, v1.9, v2.0 and every later release line.",
    path=path,
)
text = replace_once(
    text,
    "- Use release title `Play Store App Audit v1.6.0 (ETB Win x64)` and body heading `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`.",
    "- The current GitHub Release title is `Play Store App Audit v1.6.0 (Win x64 Only)`; the body heading remains `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`.",
    path=path,
)
insert = """### v1.7-v1.9 Windows x64 Engineering Test Build (ETB) profile

v1.7.0 is published and immutable as an unsigned Windows x64 ETB. v1.8 and v1.9 deliberately continue the same Windows x64-only distribution profile.

- Build Windows x64 only from one exact frozen `main` SHA after the required Quality gates pass.
- Use `.github/workflows/build-windows-exe.yml` with `target=x64`.
- Do not invoke production Windows signing or build Windows ARM64, Linux or macOS release candidates for v1.8 or v1.9.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- Publish exactly three project-defined assets: the Windows x64 ZIP, one consolidated third-party source `tar.xz`, and `SHA256SUMS.txt`.
- Current/future Windows x64 ETB GitHub Release titles use suffix `(Win x64 Only)`; the release-body heading still identifies `Engineering Test Build - Windows x64 Only` and the package remains clearly described as unsigned.
- v1.7.0 is frozen at `e2d09098bc42c6f16d202d010deda3eb24d99aa3`. Do not rebuild, retag or replace it.
- Any source or release-tooling change after a future v1.8/v1.9 SHA freeze invalidates that candidate and requires a rebuild from the new exact SHA.

### v2.0-or-later production profile
"""
text = replace_once(text, "### v2.0-or-later production profile\n", insert, path=path)
text = replace_once(
    text,
    "Production signing and the full six-platform release are not planned before v2.0. The implementation remains preserved for that later milestone.",
    "v2.0 is the first planned return to a full multi-platform release. Production signing remains the preferred target, but it must not be promised until provider eligibility, credentials, cost and end-to-end signing/notarization validation are confirmed.",
    path=path,
)
write(path, text)

# README.md
path = "README.md"
text = read(path)
text = replace_once(
    text,
    "The current published v1.6.0 release is a Windows x64 Engineering Test Build (ETB) and provides one prebuilt package:",
    "The current published v1.7.0 release is a Windows x64 Engineering Test Build (ETB) and provides one prebuilt package:",
    path=path,
)
text = replace_once(
    text,
    "The Windows v1.6.0 package is intentionally unsigned. Production signing and the full six-platform production release are not planned before v2.0. Microsoft Defender SmartScreen or another reputation-based check may therefore ask you to confirm that you want to run the application. That warning reflects signing and reputation status, not a finding that the application is unsafe.",
    "The Windows v1.7.0 package is intentionally unsigned. v1.8 and v1.9 will also remain Windows x64-only ETBs. v2.0 is the first planned return to multi-platform distribution; production signing is the preferred target but remains contingent on successful credential/provider validation. Microsoft Defender SmartScreen or another reputation-based check may therefore ask you to confirm that you want to run the current package. That warning reflects signing and reputation status, not a finding that the application is unsafe.",
    path=path,
)
text = replace_once(
    text,
    "Windows ARM64, Linux and macOS remain supported by the shared source tree, and the immutable v1.3.0 release remains available with Windows ARM64, Linux x64/ARM64 and macOS Intel/Apple Silicon prebuilt packages. v1.6.0 deliberately does not rebuild those targets in order to keep this ETB focused and inexpensive.",
    "Windows ARM64, Linux and macOS remain supported by the shared source tree, and the immutable v1.3.0 release remains available with Windows ARM64, Linux x64/ARM64 and macOS Intel/Apple Silicon prebuilt packages. v1.7.0 deliberately does not rebuild those targets in order to keep this ETB focused and inexpensive.",
    path=path,
)
text = replace_once(
    text,
    "The v1.6.0 release includes one consolidated third-party source archive and a release-wide `SHA256SUMS.txt` alongside the Windows x64 ZIP. All three project-defined assets were validated from the same frozen source SHA before publication and reverified after download from the published release.",
    "The v1.7.0 release includes one consolidated third-party source archive and a release-wide `SHA256SUMS.txt` alongside the Windows x64 ZIP. All three project-defined assets were validated from frozen source SHA `e2d09098bc42c6f16d202d010deda3eb24d99aa3` before publication and reverified after download from the published release.",
    path=path,
)
text = replace_once(
    text,
    "- Filter results, combine status filters and switch between Basic, Device, Technical and Custom views.\n- Compare with a previous audit and maintain device inventory history and snapshots.\n- Export all or visible results as CSV or HTML.",
    "- Filter results, combine status, installer and SDK maintenance filters, and switch between Basic, Device, Technical and Custom views.\n- Save reusable audit profiles without mixing them with result-filter state.\n- Use conservative smart/incremental re-audit behavior, targeted rechecks or an explicit Force full refresh.\n- Compare with a previous audit and maintain device inventory history and snapshots.\n- Export all or visible results as CSV, HTML or versioned JSON.",
    path=path,
)
text = replace_once(
    text,
    "| Platform | Source support | Current published v1.6.0 | Latest older prebuilt |\n| --- | --- | --- | --- |\n| Windows x64 | Supported | ETB ZIP | v1.5.0 ZIP |",
    "| Platform | Source support | Current published v1.7.0 | Latest older prebuilt |\n| --- | --- | --- | --- |\n| Windows x64 | Supported | ETB ZIP | v1.6.0 ZIP |",
    path=path,
)
text = replace_once(
    text,
    "The published v1.6.0 Windows x64 package was produced from exact commit `246acb15b8e9b2aa9155dc1c3a7c24dc32d19540` after post-merge Quality validation, then assembled and checksum-verified before and after publication.",
    "The published v1.7.0 Windows x64 package was produced from exact commit `e2d09098bc42c6f16d202d010deda3eb24d99aa3` after post-merge Quality validation, then assembled and checksum-verified before and after publication.",
    path=path,
)
text = replace_once(
    text,
    "Third-party components remain under their own licenses. Binary release packages include the applicable third-party notices and source-availability material where required. The v1.6.0 release-wide corresponding-source archive is published alongside the Windows x64 ZIP.",
    "Third-party components remain under their own licenses. Binary release packages include the applicable third-party notices and source-availability material where required. The v1.7.0 release-wide corresponding-source archive is published alongside the Windows x64 ZIP.",
    path=path,
)
text = replace_once(text, "- [v1.7 chat handoff](docs/HANDOFF_V1.7.md)", "- [v1.8 chat handoff](docs/HANDOFF_V1.8.md)", path=path)
text = replace_once(
    text,
    "The published v1.6.0 public profile used one exact `main` SHA, built only the Windows x64 ETB candidate from that SHA, validated legal/source evidence, assembled the exact three-file Windows x64 ETB asset set, then tagged and published the already validated artifacts without rebuilding.",
    "The published v1.7.0 public profile used one exact `main` SHA, built only the Windows x64 ETB candidate from that SHA, validated legal/source evidence, assembled the exact three-file Windows x64 ETB asset set, then tagged and published the already validated artifacts without rebuilding.",
    path=path,
)
write(path, text)

# CHANGELOG.md
path = "CHANGELOG.md"
text = read(path)
marker = "Notable user-facing and compatibility changes to Play Store App Audit are recorded here. Internal CI/release-process decisions belong in `AGENTS.md`, `docs/PROJECT_DECISIONS.md` and `docs/BUILDING.md`.\n\n"
section = f"""## [1.7.0] - 2026-08-23

### Added

- Responsive Details Panel placement with Auto, Right and Below modes plus adaptive content reflow.
- Structured Store diagnostics with concise market evidence, fallback outcomes and machine-readable raw evidence retained for export.
- Installer/source classification and filters, plus target/min SDK maintenance filters and compatibility-state filtering.
- Versioned JSON export for all or visible results.
- Reusable audit profiles for audit execution settings.
- Conservative smart/incremental re-audit behavior with targeted rechecks and explicit Force full refresh.

### Changed

- Store country and Store language resolution are independent; automatic phone language follows the active Android system language while country prefers explicit override, host region, Android region only as a late fallback, then US.
- User-facing Store evidence and Notes are substantially less verbose while technical evidence remains structured underneath.
- Play Store audit history and connected-device inventory history are presented separately, including first-baseline wording.
- Health Score is now presented as an optional supported maintenance heuristic, remains disabled by default and is explicitly not a security/malware rating.
- Details Panel position controls are larger and easier to understand.

### Fixed

- File/list audits do not inherit stale phone-language context.
- First-audit rows no longer misleadingly show phone inventory changes as Store-audit changes.
- Removed or region-restricted rows no longer expose raw internal machine-note tokens in the Details Panel.
- Definitive Store not-found evidence remains separate from transient/inconclusive request failures.

### Compatibility

- v1.7.0 is an unsigned Windows x64 Engineering Test Build (ETB).
- Public GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`.
- The public asset set contains exactly one Windows x64 ZIP, one consolidated third-party source archive and one `SHA256SUMS.txt`.
- Frozen source SHA: `{RELEASE_SHA}`.
- Windows x64 ZIP SHA-256: `{WINDOWS_SHA}`.
- Third-party source archive SHA-256: `{SOURCES_SHA}`.
- `SHA256SUMS.txt` SHA-256: `{SUMS_SHA}`.
- Windows ARM64, Linux and macOS remain source-supported but were not rebuilt for v1.7.0.
- v1.8 and v1.9 remain Windows x64-only ETB release lines. v2.0 is the first planned return to multi-platform distribution; production signing is a target, not yet a guarantee.

"""
if "## [1.7.0]" not in text:
    text = replace_once(text, marker, marker + section, path=path)
write(path, text)

# PROJECT_DECISIONS.md
path = "docs/PROJECT_DECISIONS.md"
text = read(path)
text = replace_once(text, "### v1.7 and v1.8 Windows x64 Engineering Test Builds (ETB)", "### v1.7, v1.8 and v1.9 Windows x64 Engineering Test Builds (ETB)", path=path)
text = replace_once(text, "v1.7 and v1.8 deliberately continue the unsigned Windows x64-only Engineering Test Build profile.", "v1.7, v1.8 and v1.9 deliberately continue the unsigned Windows x64-only Engineering Test Build profile. v1.7.0 is published and immutable; v1.8 and v1.9 continue the same distribution constraint.", path=path)
text = replace_once(text, "For both release lines:", "For all three release lines:", path=path)
text = replace_once(text, "- use the `(ETB Win x64)` GitHub Release naming convention and clearly describe the package as unsigned;", "- use GitHub Release title suffix `(Win x64 Only)` while the body heading continues to identify `Engineering Test Build - Windows x64 Only`; clearly describe the package as unsigned;", path=path)
text = replace_once(text, "The v1.8 product-scope expansion does not change the distribution profile. Windows ARM64 and non-Windows release artifacts remain outside both v1.7 and v1.8.", "The v1.8 product-scope expansion and the v1.9 release line do not change the distribution profile. Windows ARM64 and non-Windows release artifacts remain outside v1.7, v1.8 and v1.9.", path=path)
text = replace_once(text, "Rationale: v1.7 and v1.8 remain focused desktop product iterations. Keeping one validated Windows x64 profile avoids unnecessary signing and multi-platform release cost before the production-distribution milestone.", "Rationale: v1.7, v1.8 and v1.9 remain focused desktop product iterations. Keeping one validated Windows x64 profile avoids unnecessary signing and multi-platform release cost before the v2.0 distribution milestone.", path=path)
text = replace_once(
    text,
    "The full six-platform production release architecture remains implemented in source but execution is deferred until **v2.0 or later**.",
    "v2.0 is the first planned return to the full six-platform production release architecture. Production signing is the preferred outcome, but public-trust signing/notarization must remain conditional until provider eligibility, credentials, cost and end-to-end verification are proven.",
    path=path,
)
text = text.replace("v1.6/v1.7/v1.8", "v1.6/v1.7/v1.8/v1.9")
text = text.replace("v1.4/v1.5/v1.6/v1.7/v1.8", "v1.4/v1.5/v1.6/v1.7/v1.8/v1.9")
write(path, text)

# PROJECT_STATUS.md rewritten to current state.
write(
    "docs/PROJECT_STATUS.md",
    f"""# Project Status

Last updated: 2026-08-23

## Published release

- Latest published version: `v1.7.0`
- Immutable release commit: `{RELEASE_SHA}`
- Release class: Engineering Test Build (ETB), Windows x64 only
- Signing: intentionally unsigned
- GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`
- Release-body heading: `Play Store App Audit v1.7.0 (Engineering Test Build - Windows x64 Only)`
- Public project-defined assets: exactly 3

Published v1.7.0 is immutable. Do not rebuild, retag, rewrite or replace its source commit, tag or assets. Earlier published releases remain immutable as well.

## v1.7.0 release evidence

The release was built, assembled, tagged, published and re-downloaded from one exact frozen `main` SHA: `{RELEASE_SHA}`.

- Final Quality push run: `32609018096`, successful on Python 3.13 and 3.14.
- Final Windows x64 build run: `32609148943`, successful on the same frozen SHA.
- Engineering release assembly run: `32610281618`, successful with the exact three-file ETB asset set.
- Publish/post-publication verification run: `32610914851`, successful.
- Annotated tag `v1.7.0` peels to the frozen SHA.
- Published assets were re-downloaded and independently checksum-verified after publication.

Published project-defined assets and SHA-256 values:

- `PlayStoreAppAudit-v1.7.0-windows-x64.zip`: `{WINDOWS_SHA}`
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz`: `{SOURCES_SHA}`
- `SHA256SUMS.txt`: `{SUMS_SHA}`

## Current development baseline

- Canonical application version: `1.7.0` until a deliberate v1.8 version freeze changes it.
- Active planning/development cycle: `v1.8`.
- Python packaging baseline: 3.13.
- Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials`: 6.11.1.
- Nuitka: 4.1.3.
- UI: Qt Widgets using the platform/default QStyle.
- Managed ADB remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers: 16.
- Store transport timeout: 25 seconds.
- v1.8 release target: Windows x64 only.
- v1.9 release target: Windows x64 only.
- v2.0 is the first planned return to multi-platform distribution. Production signing is the preferred target but is not guaranteed until provider/credential and end-to-end validation succeed.

Always verify the live `main` SHA from GitHub or a freshly generated repository snapshot rather than treating this static document as a branch pointer.

## Shipped in v1.7.0

- Responsive Details Panel with Auto/Right/Below placement and adaptive content layout.
- Independent Store country and Store language resolution with host/device fallback semantics.
- Structured per-app Store evidence and compact diagnostics with human-readable Notes.
- Installer/source classification and filtering.
- target/min SDK maintenance filters and compatibility-state filtering.
- Versioned JSON export for all/visible results.
- Saved audit profiles separated from result-filter state.
- Conservative smart/incremental re-audit behavior plus targeted rechecks and Force full refresh.
- Clear separation of Store audit history from phone inventory history and first-baseline wording.
- Health Score promoted from experimental presentation to optional supported maintenance heuristic, still disabled by default.

Play Store app icons remain experimental in v1.7.0 and are carried into v1.8 for graduation/hardening.

## v1.8 planned scope

v1.8 is a Windows x64-only UX/productivity cycle.

- Graduate Play Store icons from experimental to normal supported behavior, with any cache/CDN/offline/large-table hardening indicated by v1.7 observations.
- Add saved filters / smart queries as reusable result-filter expressions, deliberately separate from audit profiles.
- Add a richer compact dashboard / summary that complements rather than duplicates details, changes and filters.
- Details Pane UX v2: allow hide/show and test replacing the three position buttons with one compact control/menu offering Auto, Right, Below and Hide.
- Treat an Excel-like bottom `QStatusBar` as an alternative UX experiment if the primary Details Pane control concept is not attractive; possible uses include connected device/source identity, transient status and compact secondary view controls.
- Review tooltip/statusTip consistency across icon-only and non-obvious controls; do not add redundant tooltips to already self-explanatory text buttons.
- Redesign Advanced Settings because the current stacked `QGroupBox`/form presentation looks dated; favor clearer category navigation and less visual chrome while retaining native Qt widgets.
- Perform a full menu/button/iconography/clarity audit and produce a report before implementing broad visual changes.
- Review export-menu consistency and context-menu enable/disable behavior as part of the UX audit.

## v1.9 distribution constraint

v1.9 is also Windows x64 only. Product scope is intentionally not frozen yet, but do not introduce Windows ARM64/Linux/macOS release packaging for v1.9 unless a new explicit product decision changes the roadmap.

## v2.0 direction

v2.0 is the first planned return to Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 release distribution. Ideally Windows and macOS packages will use production-trust signing/notarization, but this remains contingent on real credential/provider eligibility, cost and successful end-to-end validation. CLI/headless work remains v2.0-or-later scope.

## Explicitly removed / not planned

Do not reintroduce without a new explicit product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country-set presets.

## Durable release and repository invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only; no squash/rebase project history.
- Before any local pull, run `git status --short`; if dirty, stop rather than resetting, stashing or discarding automatically.
- Published releases are immutable.
- Every release profile derives all artifacts from one exact frozen SHA.
- Quality validation comes before freezing a release SHA; tag only after artifact validation; tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- ADB remains read-only with respect to installed Android apps.
- Every release finishes the permanent closure procedure in `RELEASE_CLOSURE.md`, including post-release context updates and safe local VS Code synchronization.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `HANDOFF_V1.8.md` for durable policy, planning and continuation context.
""",
)

# ROADMAP.md rewritten for the new active cycle.
write(
    "docs/ROADMAP.md",
    f"""# Product Roadmap

Last updated: 2026-08-23

## Purpose

This file is the canonical forward-looking product roadmap for Play Store App Audit. `PROJECT_STATUS.md` records current shipped state, `PROJECT_DECISIONS.md` records durable engineering/release policy, and this document assigns future product work.

## Planning rules

- Preserve the exact-SHA release model, read-only ADB policy and Store correctness semantics unless a deliberate decision changes them.
- Do not silently move deferred or rejected ideas into active scope.
- Published releases, tags and assets are immutable.
- Produce a UX audit/report before broad visual redesign work when the change is exploratory rather than already specified.

## v1.7 published baseline

v1.7.0 is published and immutable as an unsigned Windows x64 Engineering Test Build.

- Frozen release source SHA: `{RELEASE_SHA}`.
- GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`.
- Public project-defined assets: Windows x64 ZIP, consolidated third-party source archive and `SHA256SUMS.txt`.
- Release evidence and checksums are recorded in `PROJECT_STATUS.md` and `HANDOFF_V1.8.md`.

## v1.8 active scope

v1.8 is the next feature/polish cycle and remains Windows x64 only. Do not build or publish Windows ARM64, Linux or macOS v1.8 release candidates.

### Graduate Play Store icons from experimental

Move Store icons from experimental/opt-in framing to normal supported behavior if v1.7 observations do not reveal a blocking issue. Finish any required cache growth, CDN failure, stale-data, offline reuse or large-table responsiveness hardening.

### Saved filters / smart queries

Add reusable result-filter expressions that remain distinct from saved audit profiles. Example concepts include `Removed from Play AND still installed`, `Stale AND sideloaded`, target-SDK thresholds and installed/Store-version differences. Define the UX deliberately before implementation rather than reviving an older CRUD design automatically.

### Richer compact dashboard / summary

Design a compact at-a-glance summary against the mature Details Panel, change overview, filters and smart queries. It must add information rather than duplicate existing UI.

### Details Pane UX v2

Explore a more space-efficient control model:

- allow the Details Panel to be hidden completely;
- prefer testing one compact Details control/menu instead of expanding the current three buttons to four;
- candidate menu states: Auto, Right, Below and Hide;
- keep hover help for icon-only/non-obvious controls;
- preserve Right as the current default unless testing justifies a deliberate change;
- treat `QDockWidget` as an experiment only, not a committed redesign, because it may look too traditional relative to the current card/table UI.

### Status-bar alternative experiment

If the primary Details-control concept is not visually successful, evaluate a real bottom `QStatusBar` similar to Excel's status bar as an alternative or complementary interaction surface. Possible content includes connected device/source identity on the left, transient status/progress in the middle, and compact secondary view controls on the right. Do not commit to moving Details placement controls there until the prototype is visually convincing and discoverable.

### Advanced Settings redesign

The current stacked `QGroupBox`/`QFormLayout` presentation is functionally correct but visually dated. Explore a more modern native-Qt settings structure such as category navigation on the left and a focused settings page on the right, with less boxed visual chrome. Reconsider whether purely visual settings such as columns/icons belong under View rather than Advanced Settings.

### Full UI/menu/button clarity audit

Before broad implementation, produce a report covering:

- File/View/Tools/Help menu grouping and naming;
- primary and secondary button hierarchy;
- icon consistency and use of native/modern desktop metaphors;
- tooltip policy for icon-only/non-obvious controls and `statusTip` opportunities;
- keyboard shortcuts/mnemonics where useful;
- export-menu consistency across the main button and File menu;
- right-click actions disabled when unavailable rather than silently doing nothing;
- status chips, search/filter discoverability and redundant permanent tips/legends.

Do not turn this audit into automatic code changes before the report is reviewed.

## v1.9

v1.9 is also Windows x64 only. Its detailed product scope is intentionally left open until v1.8 is evaluated. Do not reintroduce multi-platform release packaging in v1.9 without an explicit roadmap/decision change.

## v2.0 and later

### First planned return to multi-platform distribution

v2.0 is the first planned release after v1.3 to return to the full six prebuilt platform/architecture targets:

- Windows x64 and ARM64;
- Linux x64 and ARM64;
- macOS x64 and ARM64.

Production-trust signing is the ideal target for Windows and macOS, including notarization/stapling/Gatekeeper verification on macOS, but it is not yet guaranteed. Before promising signed v2.0 packages, validate provider eligibility, credentials, cost, GitHub configuration and real end-to-end signing/notarization runs.

### CLI/headless mode

Keep CLI/headless auditing in v2.0-or-later scope. A future CLI should reuse the service layer rather than turning the desktop app into a background daemon.

### Local APK audit concept

Explore a LocalAPK-inspired workflow for locally stored APK files and version comparison. Decide first whether it belongs inside Play Store App Audit or a companion utility.

### Advanced app management

Uninstall/disable/permission/clear-data/force-stop/install actions remain outside the near-term product because they conflict with the durable read-only ADB policy. Any such work requires an explicit policy change first.

## Explicitly not planned

Unless a new product decision reopens them:

- installed signing-certificate fingerprint capture/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country presets.

## Handoff requirement

The active human-readable handoff for the v1.8 cycle is `HANDOFF_V1.8.md`. Generate a new handoff ZIP only from a clean, synchronized local `main` checkout after post-release documentation is merged, using `../scripts/export_chat_handoff.ps1`.
""",
)

# BUILDING.md targeted current-profile updates.
path = "docs/BUILDING.md"
text = read(path)
text = text.replace("For the v1.4/v1.5 Windows x64 ETB profiles, the frozen v1.6 Windows x64 ETB profile, and the preserved future production profile:", "For the Windows x64 ETB profiles through v1.9 and the preserved future production profile:")
text = replace_once(
    text,
    "### v2.0-or-later full production release",
    """### v1.7-v1.9 Windows x64 Engineering Test Builds (ETB)

v1.7.0 is published and immutable as an unsigned Windows x64 ETB. v1.8 and v1.9 deliberately reuse the same exact-SHA x64-only release profile.

- Build with `.github/workflows/build-windows-exe.yml` using `target=x64` only.
- Do not invoke production Windows signing or build Windows ARM64/Linux/macOS release candidates.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- Publish exactly the Windows x64 ZIP, consolidated third-party source archive and `SHA256SUMS.txt`.
- Current/future ETB GitHub Release titles use `(Win x64 Only)`; the body heading continues to say `Engineering Test Build - Windows x64 Only`.
- v1.7.0 frozen release SHA is `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.
- v1.8 and v1.9 must freeze their own exact `main` SHA after Quality passes.

### v2.0-or-later full production release""",
    path=path,
)
text = text.replace("This procedure applies to v1.4, v1.5 and v1.6.0.", "This procedure applies to the Windows x64 ETB release line through v1.9.")
text = text.replace("For v1.4, v1.5 and v1.6.0 ETB releases, use `target=x64`.", "For Windows x64 ETB releases through v1.9, use `target=x64`.")
text = text.replace("including v1.4, v1.5 and the frozen v1.6.0 profile", "including the Windows x64 ETB profiles through v1.9")
text = text.replace("For unsigned Windows x64 engineering releases such as v1.4, v1.5 and v1.6.0", "For unsigned Windows x64 engineering releases through v1.9")
text = text.replace("v1.4, v1.5 and the frozen v1.6.0 profile deliberately remain unsigned Windows x64 engineering releases.", "The Windows x64 ETB release line through v1.9 deliberately remains unsigned.")
text = text.replace("application version `1.6.0` maps to Windows version `1.6.0.0`", "application version `1.7.0` maps to Windows version `1.7.0.0`")
text = text.replace("v1.6.0 version metadata is part of the frozen release profile. Do not change it during release execution.", "v1.7.0 version metadata is part of its immutable published release profile. Future v1.8/v1.9 version changes belong to their own deliberate release freeze.")
write(path, text)

# RELEASE_NOTES.md: durable title convention + published v1.7 body.
path = "docs/RELEASE_NOTES.md"
text = read(path)
text = replace_once(
    text,
    "For example, the v1.4/v1.5 Windows x64 Engineering Test Build profile uses the title suffix `(ETB Win x64)` and must clearly identify the package as unsigned.",
    "Current and future Windows x64 Engineering Test Build releases use the GitHub Release title suffix `(Win x64 Only)` and must clearly identify the package as unsigned. Historical titles may retain older wording where that reflects the published record.",
    path=path,
)
if "## Published v1.7.0 release body" not in text:
    text += f"""

## Published v1.7.0 release body

The body below records the final v1.7.0 release wording and successful evidence. The published tag, source commit and three assets are immutable.

```markdown
## Play Store App Audit v1.7.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Added
- Responsive selected-row Details Panel controls with Auto, Right and Below placement modes and adaptive content layout.
- Structured Store request evidence and compact diagnostics for country/language checks, fallback markets and inconclusive results.
- Installer/source classification and built-in installer filters.
- SDK maintenance filters and compatibility-state filtering.
- Versioned JSON export for all or visible results.
- Reusable audit profiles.
- Conservative smart/incremental re-audit behavior with targeted rechecks and Force full refresh.

### Changed
- Store country and Store language are resolved independently with explicit override/host/device fallback semantics.
- Store market evidence and Notes prioritize concise human-readable outcomes while raw evidence remains structured.
- Store audit history and phone inventory history are presented separately, including first-baseline wording.
- Health Score is an optional supported 0-100 maintenance heuristic, disabled by default and not a malware/security score.
- Details Panel position controls are larger and clearer while retaining hover tooltips.

### Fixed
- File/list audits no longer inherit stale connected-phone language context.
- First-audit rows no longer present phone inventory changes as previous Store-audit changes.
- Removed/region-restricted apps no longer expose raw machine-note tokens in the user-facing Details Panel.
- Definitive Store not-found evidence remains distinct from transient/inconclusive failures.

## Compatibility and distribution
- Engineering Test Build (ETB), Windows x64 only.
- The Windows package is intentionally unsigned; Windows may display a SmartScreen/publisher warning.
- Windows ARM64, Linux and macOS remain source-supported but were not rebuilt for v1.7.0.
- Python 3.13 is the packaging baseline; Python 3.13 and 3.14 are Quality CI targets.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- Managed ADB remains read-only with respect to installed Android apps.

## Release assets
- `PlayStoreAppAudit-v1.7.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

## Verification
- Frozen source SHA: `{RELEASE_SHA}`.
- Quality push run `32609018096` passed on Python 3.13 and 3.14.
- Windows x64 build run `32609148943` succeeded on the same frozen SHA.
- Engineering assembly run `32610281618` validated the exact x64-only three-file set.
- Publish/post-publication verification run `32610914851` re-downloaded all three public assets, verified their checksums and confirmed annotated tag `v1.7.0` peels to the frozen SHA.
- Windows x64 ZIP SHA-256: `{WINDOWS_SHA}`.
- Third-party source archive SHA-256: `{SOURCES_SHA}`.
- `SHA256SUMS.txt` SHA-256: `{SUMS_SHA}`.
```
"""
write(path, text)

# CI_MAINTENANCE.md title convention.
path = "docs/CI_MAINTENANCE.md"
text = read(path)
text = replace_once(text, "- GitHub Release title suffix: `(ETB Win x64)`", "- GitHub Release title suffix: `(Win x64 Only)`", path=path)
write(path, text)

# Mark v1.7 handoff as historical/closed.
path = "docs/HANDOFF_V1.7.md"
text = read(path)
if "Status: v1.7.0 published" not in text:
    text = replace_once(
        text,
        "# Play Store App Audit v1.7 Chat Handoff\n\n",
        "# Play Store App Audit v1.7 Chat Handoff\n\nStatus: v1.7.0 published and immutable. Active continuation moved to `docs/HANDOFF_V1.8.md`.\n\n",
        path=path,
    )
write(path, text)

# New v1.8 handoff.
write(
    "docs/HANDOFF_V1.8.md",
    f"""# Play Store App Audit v1.8 Chat Handoff

Last updated: 2026-08-23

## Purpose

This is the canonical human-readable handoff for the v1.8 development cycle after successful publication of v1.7.0. Read it with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `RELEASE_CLOSURE.md`.

## Immutable v1.7.0 baseline

- Release: `v1.7.0`
- GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`
- Release class: unsigned Windows x64 Engineering Test Build (ETB)
- Frozen source SHA: `{RELEASE_SHA}`
- Quality push run: `32609018096`
- Final Windows x64 build run: `32609148943`
- Engineering assembly run: `32610281618`
- Publish/post-publication verification run: `32610914851`

Published project-defined assets:

- `PlayStoreAppAudit-v1.7.0-windows-x64.zip` — SHA-256 `{WINDOWS_SHA}`
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz` — SHA-256 `{SOURCES_SHA}`
- `SHA256SUMS.txt` — SHA-256 `{SUMS_SHA}`

The annotated `v1.7.0` tag peels to the frozen SHA and all three public assets were re-downloaded and checksum-verified after publication. Do not rebuild, retag or replace them.

## Current technical baseline

- Canonical app version remains `1.7.0` until a deliberate v1.8 release/version freeze.
- Python packaging baseline: 3.13; Quality CI: 3.13 and 3.14.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- Qt 6 / PySide6 Qt Widgets using platform/default QStyle.
- ADB remains read-only with respect to installed Android apps.
- Google Play remains behind the service boundary.
- Store workers default/recommended 16; allowed advanced range 4-32; Store timeout 25 seconds.
- v1.8 and v1.9 releases are Windows x64 only and intentionally unsigned unless a new explicit product decision changes that.
- v2.0 is the first planned return to multi-platform distribution; production signing is an ideal target but is not guaranteed until real provider/credential and end-to-end validation succeeds.

## v1.7 features available as the v1.8 base

- responsive Details Panel with Auto/Right/Below placement and adaptive content layout;
- independent Store country/language semantics;
- structured Store evidence with concise user-facing diagnostics/Notes;
- installer/source classification and filters;
- SDK maintenance filters;
- versioned JSON export;
- saved audit profiles;
- conservative smart/incremental re-audit plus targeted rechecks and Force full refresh;
- separate Store-audit and phone-inventory history semantics;
- optional supported Health Score maintenance heuristic, disabled by default.

## v1.8 active scope

### Play Store icons

Graduate Play Store icons from experimental to normal supported behavior, subject to final cache/CDN/offline/large-table hardening from v1.7 observations.

### Saved filters / smart queries

Implement reusable result-filter expressions, deliberately separate from saved audit profiles. Define the UX before implementation.

### Richer compact dashboard / summary

Add useful at-a-glance information without duplicating Details Panel, change overview or filter state.

### Details Pane UX v2

The current Auto/Right/Below buttons are readable and already have hover tooltips, but they consume too much header space. Explore:

- ability to hide the Details Panel completely;
- one compact Details control/menu instead of expanding three buttons to four;
- candidate states Auto / Right / Below / Hide;
- keep platform-native Qt styling and avoid unnecessary theme dependencies;
- `QDockWidget` only as an experiment, not a predetermined solution.

### Status bar alternative

The user specifically means an Excel-like bottom status bar. Treat a true Qt `QStatusBar` as an alternative if the primary Details-control solution is not visually successful, not as a committed design. Possible uses: connected device/source identity on the left, transient status/progress centrally, compact secondary view controls on the right.

### Advanced Settings redesign

The current functional layout looks old-style. Explore category navigation plus focused pages, less stacked `QGroupBox` chrome, and moving purely visual settings to View where appropriate.

### Full UX audit before broad changes

Produce a report before implementing broad visual changes. Review all menus, buttons, icons, tooltips/statusTips, shortcuts/mnemonics, export consistency, context-menu disabled states, status chips, search/filter discoverability and permanent tips/legends. Do not automatically implement the audit findings until reviewed.

## v1.9 and v2.0 distribution roadmap

- v1.9: Windows x64 only; detailed product scope not frozen yet.
- v2.0: first planned return to Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 prebuilt releases.
- Ideally Windows/macOS will be production signed/notarized in v2.0, but do not promise that until eligibility, credentials, cost and end-to-end workflows are validated.
- CLI/headless work remains v2.0-or-later.

## Explicitly removed / not planned

Do not reintroduce without a new product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined country presets such as DACH/EU/worldwide.

## Release and Git rules

- `main` is the only permanent branch.
- Use short-lived branches and normal merge commits; no squash/rebase project history.
- Published releases are immutable.
- Before every local pull, run `git status --short`; if dirty, stop. Never auto-stash/reset/discard/clean user work.
- Every release uses one exact frozen SHA and tags only after artifact validation.
- Tag pushes do not rebuild binaries.
- Keep strict legal/source validation fail-closed.
- Windows x64 ETB GitHub Release titles now use `(Win x64 Only)`; body headings continue to identify `Engineering Test Build - Windows x64 Only`.
- Finish every release through `RELEASE_CLOSURE.md`, including post-release docs and safe local VS Code synchronization.

## Starting the v1.8 development chat

After this post-release documentation PR is merged, synchronize the local VS Code checkout safely to canonical `main` and verify it is clean. Only then run `scripts/export_chat_handoff.ps1`; it automatically selects the newest `docs/HANDOFF_V*.md`, so the resulting ZIP should be a v1.8 handoff and include a freshly generated `REPOSITORY_SNAPSHOT.md`.
""",
)

# No semantic change required in RELEASE_CLOSURE.md or export_chat_handoff.ps1;
# the exporter already discovers the newest versioned handoff automatically.
