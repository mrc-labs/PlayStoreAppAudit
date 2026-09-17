# Store App Audit v2.1 — release handoff

Last updated: 2026-09-17 CEST

This is the canonical continuation handoff for the final v2.1 work, replacing the older Track C handoff content.

Use this document as the durable starting point for a fresh ChatGPT/control-tower session, but always verify live GitHub state before consequential decisions because PRs, workflow runs and `main` may have advanced after this file was written.

### Lifecycle / retirement rule

This file is a **temporary release-cycle handoff**, not a permanent source of truth for post-v2.1 development.

After v2.1.0 has been published, independently reverified and the permanent release-closure procedure in `docs/RELEASE_CLOSURE.md` is complete, `docs/HANDOFF_V2.1.md` may — and preferably should — be deleted so stale branch/SHA/session state does not remain in the maintained documentation set.

Before deleting it, explicitly verify that every durable fact introduced during v2.1 has been migrated to the appropriate permanent source:

- published release evidence and final toolchain state → `docs/PROJECT_STATUS.md`;
- future milestone/deferred work → `docs/ROADMAP.md` and/or a dedicated GitHub issue;
- durable architectural/product decisions → `docs/PROJECT_DECISIONS.md`;
- permanent engineering/release invariants → `AGENTS.md`;
- build/release procedure changes → `docs/BUILDING.md`, `docs/RELEASE_COMPONENT_FRESHNESS.md`, `docs/RELEASE_CLOSURE.md` or `docs/RELEASE_NOTES.md` as appropriate;
- release history → `CHANGELOG.md` / published GitHub Release;
- active follow-up work → its own GitHub issue rather than this handoff.

No post-v2.1 roadmap item or permanent decision should intentionally exist only in this handoff. If the final closure review finds one, migrate it before deleting the file. Current future-facing items are already tracked elsewhere: CLI/headless and Named Custom Views in the roadmap/status documents, broader Device Specific work in #153/follow-up issues, trust/signing work in #154, and the Local APK Device Specific release blocker in #185.

Do **not** delete this file before v2.1 release closure while it is still the active cross-chat continuation context.

---

## 1. Repository and immutable release boundary

Repository: `mrc-labs/PlayStoreAppAudit`

Visible product name: **Store App Audit**.

Compatibility/technical slug remains `PlayStoreAppAudit`.

Latest published release: **v2.0.0**.

Published v2.0.0 is immutable:

- frozen source SHA: `f6530eeecd88df552c616dbb42dd78e867ae7db3`
- annotated tag: `v2.0.0`
- final production targets: Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Intel/x64 and macOS Apple Silicon/ARM64
- project-defined release assets: six platform ZIPs, one consolidated third-party source archive and `SHA256SUMS.txt`
- Windows and Linux packages are unsigned
- macOS packages use ad-hoc engineering signing only; they are not Developer ID signed/notarized
- do not rebuild, retag, rewrite or replace the v2.0.0 source commit, tag, release body or assets

Current source application version remains **`2.0.0`** until the deliberate v2.1 release-version bump.

Do not change it casually during feature/polish work.

---

## 2. Live v2.1 checkpoint at handoff creation

### Canonical `main`

`main` immediately before PR #184 is:

`4baa471b7624710f1f44475b2e5cfc8273fcaf60`

That is the normal merge commit for completed dark-mode issue #177 / PR #183.

### Active screenshot/help branch

Branch:

`v2/canonical-screenshots-help`

Current branch head before this handoff-document commit:

`8e633c3b64c66288b87bfaa94be19c3fce9eb2e2`

PR:

- **#184 — `v2.1: add canonical screenshots and in-app overview`**
- base: `main`
- state at checkpoint: **open, draft, mergeable**
- issue: **#169 — automated canonical screenshots for README and in-app Help**

Quality on the current functional head:

- **Quality - Qt6 #487: SUCCESS** on `8e633c3b64c66288b87bfaa94be19c3fce9eb2e2`

Because this handoff itself is committed after that SHA, verify the new PR head and its resulting Quality run before merging.

### Important: do not assume #184 is ready until visual re-check

The user visually accepted the packaged Help functionality and menu structure, but the screenshots initially looked too soft/small because the Overview HTML forced every image to `width="700"`.

That was fixed in commit:

`8e633c3b64c66288b87bfaa94be19c3fce9eb2e2`

Commit message:

`Preserve native resolution in Help screenshots`

The fix removes the forced 700px downscale so Qt can display the canonical PNGs at native resolution rather than resampling detailed UI text down to roughly half width.

Validation on that commit:

- focused Help tests: `28 passed`
- full pytest: `1485 passed, 6 skipped`
- Ruff: PASS
- tree clean after push
- Quality #487: SUCCESS

The remaining #169 human gate is therefore:

1. run/open the current-head app;
2. open `Help > Store App Audit Overview…`;
3. confirm the four screenshots are now materially more readable at native resolution;
4. confirm no broken images, bad clipping or unacceptable layout;
5. inspect the branch README `Screenshots` section on GitHub and confirm the 2x2 gallery renders correctly;
6. if accepted, update PR #184 body to current evidence/head, mark Ready, and merge normally with exact-head protection.

A full packaged rebuild is not strictly necessary just to prove that removing an HTML `width` attribute works: packaged image resolution/resource lookup was already proven on the immediately preceding commit and packaging code did not change. The final feature-complete Windows x64 acceptance after blocker #185 will rebuild the app again anyway. If strict exact-head PR acceptance is preferred, rebuilding #184 is also acceptable.

---

## 3. #169 / PR #184 — what is already implemented

Issue #169 goal: reproducible real-Qt screenshots for README and in-app Help, with synthetic/privacy-safe data, before v2.1 release freeze.

### Stage 1 — deterministic canonical screenshot generation

Implemented in PR #184.

New generator:

`tools/generate_canonical_screenshots.py`

Canonical committed PNGs:

- `docs/images/store-app-audit-phone-maintenance.png` — 1560x900
- `docs/images/store-app-audit-local-apk.png` — 1560x900
- `docs/images/store-app-audit-changes-history.png` — 820x720
- `docs/images/store-app-audit-mass-rename.png` — 1080x640

The generator:

- uses the real PySide6/Qt UI rather than mock screenshots;
- uses deterministic synthetic fictional rows under `com.example.*`;
- uses temporary synthetic package files for Local APK/Mass Rename state;
- does not use the user's phone inventory, APKs, account data, real famous app names or third-party artwork;
- blocks/avoids network dependency;
- avoids requiring a connected ADB device;
- writes only documentation screenshots, not application data;
- has a canonical Windows x64 path plus headless structural smoke coverage.

Stage 1 commit:

`1672e21b9638506fcac35fd27cc2dbcfcfc97086`

### Stage 2 — README / Help / packaging reuse

Implemented in PR #184.

Main additions:

- concise README 2x2 screenshot gallery;
- `Help > Store App Audit Overview…`;
- practical user-question-first Overview text;
- same four PNGs reused in source and packaged builds;
- runtime resolver in `playstore_app_audit/resources.py`;
- package inclusion as `help-images` on Windows/Linux/macOS;
- exact name/dimension/SHA-256 packaged-resource validator;
- packaged smoke proving runtime Help can resolve all four images;
- macOS bundle normalization moves `help-images` from `Contents/MacOS` to `Contents/Resources/help-images` when needed.

Stage 2 main commit:

`3b43ecef5109f397bec1b85dbaf027a3acafc46d`

Native-resolution readability follow-up:

`8e633c3b64c66288b87bfaa94be19c3fce9eb2e2`

### Windows x64 packaged evidence already proven for #169

A real private Windows x64 Nuitka standalone build passed on `3b43ecef5109f397bec1b85dbaf027a3acafc46d`.

Toolchain used:

- Python `3.14.6` AMD64
- PySide6 `6.11.2`
- Nuitka `4.2.1`
- MSVC/cl 14.3 backend

Gates passed:

- Nuitka standalone build: PASS
- all four `help-images` included by Nuitka: PASS
- production Device Specific profile resources: PASS
- canonical Help resource validator on raw `.dist`: PASS
- standalone contents validator: PASS
- PE architecture `IMAGE_FILE_MACHINE_AMD64 (0x8664)`: PASS
- Windows FileVersion/ProductVersion `2.0.0.0`: PASS, intentionally still development version
- packaged smoke: PASS
- versioned package resource validation: PASS
- final package validation: PASS
- final ZIP creation: PASS
- source tree remained clean

Acceptance ZIP SHA-256 for that private non-release build:

`2b6e8c2d87c0fd6248ac938a9b8a38ac34364c294edf17caaecb5ea7aa988471`

This ZIP is evidence only, **not a release artifact**.

---

## 4. New v2.1 release blocker discovered during acceptance

New issue:

**#185 — `v2.1 blocker: apply Device Specific resolver to Local APK audits`**

Parent: #153.

### User-observed behavior

During final Windows x64 acceptance:

- Device Specific resolution works very well with **Scan Phone with ADB**;
- Device Specific resolution does **not** work correctly for **Local APK/package files**.

This must be investigated/fixed before v2.1 release freeze unless investigation proves an already-equivalent intended path.

Do not defer this silently to v2.2: it is a consistency gap in an already-advertised v2.1 capability.

### Strong initial code hypothesis — verify, do not assume

The production Device Specific core itself is probably not the problem because Scan Phone works and Track C already passed live/packaged validation.

Current code evidence indicates:

- the normal/device audit path calls `device_specific_integration.enrich_rows_with_device_specific_resolution(...)` from `playstore_app_audit/ui/device_window.py`;
- `playstore_app_audit/services/local_apk_audit.py` builds the Local APK relationship directly from raw `play_version` through `device_metadata.compare_versions(...)`;
- no equivalent Local APK Device Specific integration hook was found during the initial handoff investigation.

Therefore first investigate whether Local APK rows simply never receive the additive resolver pass, and whether relationship calculation needs to consume the already-separate resolved evidence.

Do **not** create a separate Local-APK-specific resolver implementation if the existing coordinator can be reused.

### Files to inspect first for #185

At minimum:

- `playstore_app_audit/services/device_specific_integration.py`
- `playstore_app_audit/services/device_specific_resolver.py`
- `playstore_app_audit/services/device_specific_cache.py`
- `playstore_app_audit/ui/device_window.py`
- `playstore_app_audit/services/local_apk_audit.py`
- `playstore_app_audit/domain/local_artifact_store.py`
- `playstore_app_audit/ui/main_window.py`
- `playstore_app_audit/ui/details_panel.py`
- `playstore_app_audit/services/version_relationship.py`
- existing Device Specific tests, especially `tests/test_device_specific_integration.py`
- existing Local APK audit/source tests

### #185 contracts that must remain intact

Preserve Track C semantics:

- raw public Store evidence remains authoritative and must never be overwritten;
- invoke the resolver only for exact Device Specific triggers;
- resolved `versionName`, `versionCode`, profile and resolver status remain separate evidence;
- resolver failure never fails an otherwise successful audit;
- ordinary Store rows cause zero resolver network traffic;
- reuse existing resolver endpoint/profile/cache configuration;
- no APK purchase/delivery/download;
- no Google password/token/cookie/AAS/bearer/GSF/device serial persistence or exposure;
- prefer resolved positive `versionCode` for ordering when safely comparable;
- otherwise preserve conservative `Device Specific` / `Unknown` behavior.

For Local APK specifically, use the local artifact's available version-code evidence when safe rather than falling back unnecessarily to string-only versionName comparison.

### #185 required acceptance

- focused tests prove Local APK Device Specific resolver invocation;
- ordinary Local APK Store rows cause zero resolver activity;
- resolver failure preserves successful raw Store and Local APK evidence;
- raw `play_version` remains unchanged;
- resolved evidence remains separate and visible/exportable according to existing Track C conventions;
- Local APK relationship is correct/conservative;
- Scan Phone behavior remains unchanged;
- full pytest + Ruff PASS;
- Windows x64 packaged acceptance includes at least one real/synthetic Local APK Device Specific scenario before v2.1 freeze.

---

## 5. Completed v2.1 product tracks

### Track A — Local APK quick-filter UI polish

Completed.

### Track B — Local APK file management

Completed.

B1:

- single-file Rename / Remove;
- physical-path identity;
- safe no-overwrite behavior;
- explicit confirmation;
- no Store re-audit after mutation.

B2:

- Mass Rename core + preview/dialog/session integration;
- mutation-free planning;
- tokens `{packagename}`, `{appname}`, `{playname}`, `{category}`, `{localversion}`;
- full-batch portable/case-normalized collision detection;
- safe swap/cycle handling through temporary same-directory names;
- execution revalidates preview assumptions.

B3:

- `Remove All Outdated…`;
- `Remove All Unknown…`;
- mutation-free preview;
- permanent-delete confirmations;
- exact relationship semantics;
- session synchronization without Store re-audit/APK reparse.

### Track C — Device Specific resolver production scope

Completed before the #185 Local APK integration gap was discovered.

PoC:

- #176 / PR #178.

Production core:

- #179 / PR #180.

Production integration:

- #181 / PR #182.
- merged to `main` as `f58cf7cbd8ceb78c9160f7aab1a2056f57091bac`.

Production profiles intentionally remain limited to:

- OnePlus 8 Pro EEA — Android 10 / API 29;
- Samsung Galaxy S20+ — Android 13 / API 33.

Do not casually expand profiles during v2.1 release closure.

Still deferred beyond v2.1 unless a blocker requires otherwise:

- privacy-safe `Your Device` full Play-profile capture;
- Google/AAS end-user authentication / advanced session UX;
- extra unvalidated production profiles;
- public/default dispenser service.

### #177 — dark-mode semantic palette / contrast

Completed and merged through PR #183.

Merge commit:

`4baa471b7624710f1f44475b2e5cfc8273fcaf60`

Quality #483: SUCCESS.

Controlled Windows x64 light/dark visual acceptance: PASS.

---

## 6. Exact next sequence from this handoff

The fresh chat should not invent a new roadmap. Continue in this order unless live GitHub state proves that a step has already happened.

### Step 1 — verify live state

Use the GitHub connector first.

Verify:

- current `main` SHA;
- PR #184 state/head;
- current Quality result on the handoff-updated PR head;
- issue #169 state;
- issue #185 state;
- issue #153 remains the v2.1 master issue.

Do not rely on this document alone for mutable state.

### Step 2 — finish #169 / PR #184

If PR #184 is still open:

1. perform the native-resolution visual re-check on the latest head;
2. confirm GitHub README 2x2 gallery;
3. review final PR diff;
4. verify latest Quality is green;
5. update PR body with final evidence/head if stale;
6. mark Ready;
7. merge with **normal merge commit**, exact expected-head SHA;
8. confirm #169 closes as completed;
9. update #153 with a transition checkpoint.

Do not squash or rebase.

### Step 3 — fix blocker #185

From the new merged `main`:

1. inspect the Local APK flow and existing Device Specific coordinator;
2. define the smallest integration fix;
3. create one focused short-lived branch/PR for #185;
4. add tests before/with implementation;
5. preserve all Track C privacy/security/raw-evidence contracts;
6. run focused tests, full pytest, Ruff, Quality;
7. perform Windows x64 packaged acceptance for Local APK Device Specific behavior;
8. merge normally with exact-head protection;
9. update #153.

Avoid Codex unless it clearly reduces work without losing control. This gap is probably small enough for direct implementation/review.

### Step 4 — feature-complete Windows x64 v2.1 acceptance

After #185 is merged, treat product feature scope as frozen unless acceptance finds a real blocker.

Build the current development version on native Windows x64 and validate:

- source/full tests and Ruff;
- standalone contents;
- AMD64 PE architecture;
- runtime resources including Device Specific profiles and Help images;
- packaged smoke;
- Local APK workflows including #185;
- Scan Phone Device Specific behavior;
- dark/light readability;
- canonical Help/README surfaces;
- no regression to file-management actions.

This is a feature-complete acceptance build, not yet the final public v2.1 artifact if the canonical version is still `2.0.0`.

### Step 5 — enter formal v2.1 release preparation

Only after feature-complete Windows x64 acceptance:

1. run the **release-phase-entry component freshness gate**;
2. resolve/update any maintained component that is no longer latest stable, then rerun all affected validation;
3. create a focused release-prep branch from accepted `main`;
4. bump canonical version deliberately to `2.1.0`;
5. update `CHANGELOG.md` and draft the v2.1 GitHub Release body using `docs/RELEASE_NOTES.md` structure;
6. update maintained project-context docs whose v2.1 facts changed.

Do not create a public RC tag.

### Step 6 — pre-freeze gate and exact release SHA

Immediately before freezing the release SHA:

1. run the **second mandatory component freshness gate**;
2. run exact-head Quality;
3. ensure release docs/version/legal tooling are final;
4. select one exact full `main` SHA only after those gates pass.

If source or release tooling changes after freeze, discard that candidate and repeat affected gates. Never mix artifacts from different SHAs.

### Step 7 — six-platform exact-SHA release gate

Build from the same frozen SHA:

- Windows x64
- Windows ARM64
- Linux x64
- Linux ARM64
- macOS Intel/x64
- macOS Apple Silicon/ARM64

Use the canonical manual GitHub Actions workflows with `expected_sha` exact-match protection.

Any shared/platform fix changes source and therefore invalidates the prior candidate SHA. Merge the fix, rerun required Quality/freshness/acceptance, then freeze a new SHA and rebuild the affected/final target set according to release invariants.

### Step 8 — assemble and publish v2.1.0

Expected project-defined public asset model follows the v2.0 six-platform profile unless a deliberate engineering decision changes it:

1. Windows x64 ZIP
2. Windows ARM64 ZIP
3. Linux x64 ZIP
4. Linux ARM64 ZIP
5. macOS x64 ZIP
6. macOS ARM64 ZIP
7. consolidated third-party source archive
8. `SHA256SUMS.txt`

Before publication:

- canonical assembler validates exact-SHA lineage;
- exact asset names/count pass;
- SHA256SUMS independently validates all project-defined assets;
- clean extraction/re-download validators pass;
- signing/notarization claims reflect actual evidence only.

Then:

- create annotated `v2.1.0` tag only after the exact SHA/assets are accepted;
- publish the already-validated assets; tag pushes must not rebuild binaries;
- re-download public release assets into a clean directory;
- verify names, byte sizes and SHA-256 byte-for-byte against the accepted set.

### Step 9 — permanent release closure

Publishing is not the end.

Follow `docs/RELEASE_CLOSURE.md`:

- update maintained project-context Markdown;
- update `PROJECT_STATUS.md` with exact v2.1 release evidence;
- update roadmap/decisions only where facts changed;
- close/update #153 appropriately;
- verify repository Actions retention/housekeeping as required;
- on the user's local VS Code checkout, first verify `git status --short` is clean;
- `git fetch --prune origin`;
- switch to `main`;
- `git pull --ff-only origin main`;
- verify local `HEAD` equals canonical post-release `main`;
- only then regenerate repository snapshot / future handoff.

Never auto-reset, stash or discard a dirty user working tree.

---

## 7. Release documentation — what to read and why

A fresh chat should read these in this order before formal release work.

### Current truth / governance

#### `docs/HANDOFF_V2.1.md`

This file. Current continuation state and exact next actions.

#### `AGENTS.md`

Hard engineering/release invariants, architecture boundaries, freshness policy, exact-SHA rules, immutable release policy, release-note structure and permanent release closure requirements.

#### `docs/PROJECT_STATUS.md`

Current published-release evidence, toolchain pins, release run IDs/artifact hashes and current development baseline. The older v2.1 planning prose inside it may lag this handoff; preserve historical facts but refresh current-state sections during release closure.

#### `docs/ROADMAP.md`

Current milestone assignment and deferred work. If old version-specific scheduling text elsewhere conflicts, the roadmap plus durable decisions take precedence for current planning.

#### `docs/PROJECT_DECISIONS.md`

Durable decisions that should not be casually reversed during release engineering.

### Build / release procedure

#### `docs/BUILDING.md`

Canonical build procedures, toolchain baseline, package workflows, exact `expected_sha` behavior, local Windows x64 helper and release-candidate workflow descriptions.

Current baseline to preserve unless freshness changes it deliberately:

- Python 3.14
- `PySide6-Essentials==6.11.2`
- `pyaxmlparser==0.3.31`
- `Nuitka==4.2.1`
- current runtime pins from `pyproject.toml` / requirements

#### `docs/RELEASE_COMPONENT_FRESHNESS.md`

Mandatory twice-per-release stable-component verification procedure:

- once at release-phase entry;
- again immediately before exact-SHA freeze.

Do not skip it because Quality/builds are green.

#### `docs/RELEASE_CLOSURE.md`

Mandatory permanent post-publication closure and local VS Code synchronization procedure.

#### `docs/RELEASE_NOTES.md`

Canonical GitHub Release body structure. Required top-level order:

1. `What's New / Highlights`
2. `Compatibility and distribution`
3. `Release assets`
4. `Verification`

Optional `Added`, `Changed`, `Fixed` live inside the first section and empty headings are omitted.

#### `CHANGELOG.md`

Release history. Add the v2.1 entry without rewriting immutable historical claims.

### Useful v2.0 historical playbook/evidence

These are useful examples of the immediately preceding full six-platform release, but historical scheduling/status text is not current v2.1 state.

#### `docs/V2_0_RELEASE_PREP.md`

Excellent procedural checklist for release prep, Windows-first human acceptance, freeze invalidation and six-platform publication sequencing.

#### `docs/V2_0_RELEASE_ENTRY_FRESHNESS.md`

Example release-entry freshness evidence.

#### `docs/V2_0_FINAL_PRE_RELEASE_FRESHNESS.md`

Example final pre-freeze freshness evidence.

Use their procedure/evidence style, not stale “v2.0 not yet published” wording.

---

## 8. GitHub Actions / release tooling map

Normal source correctness:

- `.github/workflows/quality.yml`

Heavy package workflows are manual/deliberate:

- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`

Six-platform assembly:

- `.github/workflows/assemble-release.yml`

Windows engineering-only historical assembler:

- `.github/workflows/assemble-windows-engineering-release.yml`

Do not use the engineering-only assembler for the final six-platform v2.1 production-profile release.

Important release scripts include:

- `.github/scripts/build_windows_standalone.ps1`
- `.github/scripts/validate_windows_standalone.py`
- `.github/scripts/validate_device_specific_profile_resources.py`
- `.github/scripts/validate_canonical_help_resources.py`
- `.github/scripts/preflight_release_legal_material.py`
- `.github/scripts/prepare_release_legal_bundle.py`
- `.github/scripts/validate_release_legal_bundle.py`
- `.github/scripts/normalize_macos_bundle.py`
- `.github/scripts/sign_macos_app.py`
- release assembly/verification helpers referenced by the workflows

Do not remove or simplify release scripts merely because several overlap conceptually. First verify actual workflow references/imports/tests.

---

## 9. Security / privacy constraints for Device Specific work

These are hard constraints for #185 and any release validation.

Never request, print, store in repository logs or persist in app state:

- user's primary Google credentials;
- Google password;
- bearer/access tokens;
- AAS/auth tokens;
- cookies;
- GSF/device identifiers;
- raw Android device serials.

Production Device Specific remains metadata-only.

No APK purchase, delivery or download belongs in the v2.1 resolver.

Resolver endpoint configuration remains explicit. No public/default endpoint is hardcoded.

Remote endpoint configuration requires HTTPS; loopback HTTP remains allowed for local/self-hosted use according to the existing Track C contract.

---

## 10. Control-tower working style

The user wants a control-tower workflow rather than open-ended planning.

Rules:

- use the live GitHub connector before consequential branch/PR/merge/release decisions;
- do not ask the user to choose the next obvious engineering step;
- make the smallest safe change and review the live diff;
- avoid spending Codex credits when direct implementation/review is straightforward;
- Windows x64 is the primary development/acceptance platform until the final cross-platform phase;
- normal PR merge commits only; no squash/rebase;
- exact expected-head protection for merges;
- do not touch the immutable v2.0.0 release/tag/assets;
- do not promise background work;
- user runs local PowerShell blocks and returns exact output when local work is needed.

PowerShell mutation blocks should use one outer:

```powershell
& {
    # commands
}
```

with explicit `$LASTEXITCODE` checks.

For generated repository text prefer Python:

```python
Path(...).write_text(..., encoding="utf-8", newline="\n")
```

Avoid PowerShell `Set-Content -Encoding utf8` for canonical repo text because it has previously caused newline/encoding noise.

Unrelated pre-existing lint debt must not be pulled into focused feature PRs merely because a broad tool invocation finds it.

---

## 11. Current test / CI evidence summary

At the current #184 functional head `8e633c3b64c66288b87bfaa94be19c3fce9eb2e2`:

- full pytest: `1485 passed, 6 skipped`
- focused native-resolution Help tests: `28 passed`
- Ruff: PASS
- GitHub Quality #487: SUCCESS

Immediately preceding packaged acceptance head `3b43ecef5109f397bec1b85dbaf027a3acafc46d`:

- Stage 2 focused set: `90 passed, 4 skipped`
- full pytest: `1485 passed, 6 skipped`
- Ruff: PASS
- Quality #486: SUCCESS
- Windows x64 private standalone: PASS
- packaged smoke: PASS
- Help resource validation raw + versioned package: PASS
- source tree after build: clean

The only production-code difference from `3b43ece…` to `8e633c3…` is the Help image rendering change removing forced downscaling; packaging/resource code did not change.

---

## 12. Known non-blockers / deferred work

Do not accidentally expand v2.1 with already-deferred work.

Deferred to v2.2/later unless separately reprioritized:

- CLI/headless support;
- named Custom Views (#147);
- privacy-safe `Your Device` full Play-profile capture;
- Google/AAS advanced auth/session UX;
- broader Device Specific production profile set;
- public/default Device Specific dispenser service;
- additional Local APK convenience ideas not already required by a release blocker.

Code signing/notarization/trust expansion is tracked separately in #154 and is not automatically a v2.1 functional blocker. Do not claim trusted signing/notarization unless the real provider/credential path has been validated.

---

## 13. First actions for the next ChatGPT session

Do these, in order, without asking the user to restate project history:

1. Read this entire handoff.
2. Use the GitHub connector to verify current `main`, PR #184, issues #169/#185/#153 and current Quality status.
3. If #184 is still open, finish the native-resolution visual acceptance and merge #184 normally after green checks/diff review.
4. Confirm #169 closes and add a concise checkpoint to #153.
5. Treat #185 as the next release blocker; inspect the existing Device Specific and Local APK paths before writing code.
6. Implement #185 in one focused branch/PR with minimal semantics-preserving changes.
7. After #185 merge, perform feature-complete Windows x64 acceptance.
8. Only then enter formal v2.1 release prep/freshness/version-bump/six-platform exact-SHA publication sequence.

Do not skip directly to version bump or six-platform release builds while #185 remains unresolved.

---

## 14. One-line state summary

**v2.1 feature work is essentially complete; finish/merge screenshot/help PR #184, fix Local APK Device Specific blocker #185, pass feature-complete Windows x64 acceptance, then run the formal freshness → v2.1.0 bump → exact-SHA six-platform → assemble/tag/publish/closure sequence.**
