# Store App Audit v2.1 Track C Handoff

Last updated: 2026-09-15

This is the active continuation context after completion of v2.1 Track B.

## Start here

Repository: `mrc-labs/PlayStoreAppAudit`

Published v2.0.0 is immutable:

- release/tag source SHA: `f6530eeecd88df552c616dbb42dd78e867ae7db3`
- do not rebuild, retag, replace assets or rewrite the release
- Windows/Linux are unsigned
- macOS uses ad-hoc engineering signing only, not Developer ID signing/notarization

Track B code-complete main before this documentation-only handoff PR:

`f47bc14fa837f93e76a33cdf7711d080de1551fb`

The documentation/handoff PR advances `main` without changing application source. At the beginning of the next chat, verify live GitHub `main`, open PRs and Quality state before making implementation changes.

Visible product name: **Store App Audit**.

Compatibility/technical slug remains `PlayStoreAppAudit`.

Current source version remains `2.0.0` until the deliberate v2.1 version bump.

## Completed v2.1 work

### Track A

Quick-filter spacing polish completed through issue #161 / PR #162.

Store Status width was not tightened further and filter semantics were not changed.

### Track B1: single-file Local APK Rename / Remove

Core: PR #164.

UI: issue #165 / PR #166.

Properties:

- physical-path identity
- safe no-overwrite rename
- explicit remove confirmation
- exact row/candidate synchronization
- duplicate package/SHA files remain independent
- existing Store/audit evidence is preserved
- no Store re-audit after mutation

### Track B2: Mass Rename

Core planning/execution: issue #168 / PR #170.

Preview/UI/session integration: issue #171 / PR #172.

Historical template tokens:

- `{packagename}`
- `{appname}`
- `{playname}`
- `{category}`
- `{localversion}`

Important semantics:

- template planning is read-only
- original `.apk`, `.apks`, `.apkm`, `.xapk` suffix is preserved
- portable filename policy and whole-batch collision checks apply
- no unrelated destination is overwritten
- physical paths, not package/SHA identity, define files
- swaps/cycles use safe same-directory staging
- execution revalidates preview assumptions
- UI synchronizes from structured final locations
- `{category}` is reserved for genuine Store-category metadata; it is not `installer_category`
- current Store rows do not normally contain that category evidence, so missing category is an explicit plan error rather than fabricated data

### Track B3: Mass Remove

Issue #173 / PR #174.

Commands:

- `Remove All Outdated…`
- `Remove All Unknown…`

Classification is exact:

- Outdated: `local_apk_version_comparison == "Outdated"`
- Unknown: `local_apk_version_comparison == "Unknown"`

Do not broaden Unknown to `N/A`, blank, Device Specific, Not Found or another Store state.

Safety:

- mutation-free preview
- exact physical path
- supported package files only
- revalidate immediately before delete
- explicit permanent-delete confirmation
- second stronger confirmation if every active candidate would be deleted
- one failed deletion does not imply success for that file
- session removes only paths actually reported REMOVED
- final-candidate removal clears the transient Local APK source cleanly
- no Store re-audit or APK reparse

Validation at Track B closure:

- local full suite: `1283 passed, 6 skipped`
- PR Quality #460: passed
- merge commit: `f47bc14fa837f93e76a33cdf7711d080de1551fb`
- post-merge main Quality #461: passed

## Track C: Device Specific resolver

This is the next implementation track.

The normal public Store lookup remains authoritative for ordinary results.

Invoke the optional resolver only when the normal Store evidence says `Varies with device`.

### PoC gate

Do not start with production UI integration.

First build an isolated proof of concept with the conceptual contract:

`package + reference profile + auth mode -> versionName + versionCode`

Test 2-3 apps currently producing `Varies with device`.

At minimum compare coherent profiles for:

- Android 10 / API 29
- Android 13 / API 33
- Android 16 or 17 / API 36 or 37

The full intended profile set may include Android 10-17 plus **Your Device** from cached ADB metadata.

Reference profiles must be coherent real/reference device profiles, not a misleading fixed Pixel-history UI.

Potential profile evidence includes:

- brand
- model
- device
- product
- fingerprint
- API/release
- ABI
- density
- resolution
- required features where relevant

### Result semantics

Resolver output is additional evidence.

Never overwrite the raw Store fact that the package is device-specific.

Prefer `versionCode` / `longVersionCode` for ordering when available.

For **Your Device**, distinguish:

1. version currently installed
2. version Play would deliver to that device/profile

Failure must fall back safely to the existing Device Specific state.

No APK download is required when metadata/version resolution is sufficient.

Cache by package + profile + Store country + relevant resolver context.

### Authentication investigation

Two possible modes may be researched:

1. anonymous / Aurora-compatible dispenser mode
2. optional authenticated Google advanced mode

Anonymous/dispenser availability may have rate limits or reliability constraints and must degrade safely.

Any dispenser endpoint must be configurable, not hardcoded.

Avoid storing a raw Google password where a token/OAuth/AAS-style session mechanism is possible.

Do not promote either authentication path to production until the PoC demonstrates stable behavior and acceptable failure handling.

## Track D: canonical screenshots

Tracked in issue #169.

Implement after the v2.1 production UI is substantially feature-complete.

Use the same canonical screenshot set in:

- README / GitHub homepage
- an appropriate in-app Help / Getting Started / Overview surface

The README/homepage and the in-app Help/Overview introduction should lead with practical user questions, not only a feature inventory: phone-app maintenance and Store availability, local APK freshness, package-list auditing and changes over time.

Use deterministic synthetic fictional app/package data.

Do not use real user-installed apps, user APK files, personal paths or account/device identifiers.

Prefer fictional apps and original neutral/generated icons rather than famous third-party brands/logos.

Likely screenshot set, approximately 3-4 images:

1. main audit/results + Details Panel
2. Local APK/package workflow
3. Changes & History if visually useful
4. Mass Rename preview if visually useful

Canonical generation environment: Windows x64.

Prefer source-controlled Qt screenshot tooling and deterministic fixture injection. No live Store/device/account dependency. Do not auto-commit generated binaries directly from CI without visual review.

## v2.1 build/release strategy

During active feature implementation:

- Quality/source tests continuously
- packaged work primarily Windows x64
- do not continuously spend builds on all six targets

After feature completion:

1. Windows x64 packaged acceptance
2. feature freeze
3. Windows ARM64 validation
4. Linux x64/ARM64 validation
5. macOS x64/ARM64 validation
6. fix platform/shared defects
7. if source changes, rerun affected validation
8. final rebuild/validation of all six from one exact frozen SHA
9. only then tag/assemble/publish

Onefile remains a future experiment only.

Do not assume production signing/notarization. It may be claimed only after real end-to-end validation.

## Deferred / later

CLI/headless is deferred to v2.2.

When implemented it must reuse domain/service logic and must not drive Qt.

Named Custom Views issue #147 is currently a provisional v2.2 candidate, not a binding commitment.

Other later Local APK candidates:

- duplicate APK detection/management
- custom commands/integrations
- Windows Explorer integration

Do not automatically pull these into v2.1.

## Git and control-tower workflow

- `main` is the only permanent branch
- focused short-lived branches
- normal merge commits only
- no squash/rebase
- inspect GitHub live before consequential decisions
- merge only after diff review and green required checks
- delete completed short-lived branches
- keep local `main` synchronized after merges
- never modify the immutable v2.0.0 tag/release/assets

PowerShell mutation blocks should use one outer `& { ... }` scriptblock with explicit `$LASTEXITCODE` checks. A top-level pasted `throw` does not reliably prevent later separately parsed statements from running.

For generated text files use explicit UTF-8/LF writing through Python `Path.write_text(..., newline="\n")` or equivalent. Avoid `Set-Content -Encoding utf8` for canonical repository text because it previously introduced unwanted EOF/newline changes.

## Next-chat first actions

1. Verify GitHub `main` live and record the exact current SHA.
2. Verify issue #153 is the active v2.1 master issue.
3. Verify Track B issues/PRs are closed/merged and no short-lived B branch remains.
4. Read this handoff plus current `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md` and `BUILDING.md`.
5. Inspect the existing Store/service boundaries before deciding how to build the Device Specific PoC.
6. Create a focused PoC issue/branch only after the resolver/auth/profile design has been reviewed against current code.
