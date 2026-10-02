# Store App Audit v2.2.0 Release-preparation Handoff

## Current state

v2.1.0 is published, independently verified and fully closed.

- Immutable release source SHA: `df2726b959963e5dbb096638d5072bd15eb1de92`.
- Annotated tag `v2.1.0` peels to that exact SHA.
- Public release contains exactly eight project assets.
- Windows/Linux are unsigned.
- macOS is ad-hoc engineering signed only, not Developer ID signed and not notarized.
- v2.1 release coordination issue `#153` is closed as completed.
- Final post-release documentation baseline before the v2.2 kickoff docs: `fca18639480b2ce90396d860cfea34d3a9ed2771`.
- Post-merge Quality #597 / run `35803473823`: PASS on that exact SHA.
- The normal local VS Code checkout was synchronized cleanly to that baseline and the final v2.1 handoff export was generated successfully.

Published v2.1 source, tag and assets remain immutable.

The canonical application/package version is now `2.2.0`; Windows File/Product version derives as `2.2.0.0`. The published v2.1.0 version remains historical.

## v2.2 completed product pillars

All three v2.2 implementation pillars are complete and merged through PRs #214 (#208), #215 (#200) and #216 (#211). The exact main baseline before freshness work is `e204d68e2d969f7d0a30ca166243020fc115ae44`; post-merge Quality #607 / run `36754783824` passed. Master issue `#212` remains open for release validation. Do not silently add unrelated deferred work to the release.

### 1. Source-aware views and two explicit Custom layouts — #208

Preserve the existing source-aware built-in preset architecture.

The user-facing Custom concept becomes two explicit persistent layouts:

- **Custom (Phone / App List)**
- **Custom (Local APK)**

UX contract:

- both Custom entries remain discoverable in `View > Column Preset`;
- the one that does not apply to the active source may remain visible but disabled;
- Phone and imported App List sources share one Custom family;
- Local APK file/folder sources use the other;
- each family persists its own visible columns, order and widths;
- switching source family restores the matching layout and never rewrites the other;
- the existing single v2.1 Custom layout requires conservative migration with no silent loss;
- ordinary Local APK metadata remains user-configurable even when source-appropriate defaults expose APK Filename / Local APK Version;
- automatic/contextual overlays remain outside user-owned persisted Custom definitions;
- broader arbitrary named Custom Views remain separate issue `#147`.

Recommended implementation sequence:

1. source-family Custom persistence foundation and migration;
2. source-aware Custom defaults and repeated source-transition behavior;
3. final Column Preset labels/disabled states/tooltips and built-in preset UX polish.

The focused #208 implementation now completes all three steps without a broad UI redesign. It uses versioned `custom_view_layouts` schema v1 with `phone_app_list` and `local_apk` entries, preserves the stable `view_preset == "Custom"` identifier, and retains the v2.1 keys as migration/compatibility evidence. A valid legacy single Custom seeds both families once after source-safe filtering because the old schema cannot identify its originating source reliably.

Source transitions restore the matching entry under suspended header tracking. Phone and App List share one stored family, while concrete-source applicability hides phone-only fields in App List without deleting their saved widths/order. A missing family renders the active source's Basic fallback without creating a fake Custom; Reset Table Layout affects only the active family/effective layout. The three built-ins required no semantic changes.

### 2. Persistent Personal Device profile library — #200

v2.1 Personal Device capture is intentionally session-only. v2.2 promotes explicit persistent profiles into scope.

Required direction:

- allow multiple user-captured profiles;
- explicit save/consent before persistence;
- friendly local name;
- select without the physical phone connected;
- explicit refresh/replace from a connected matching device where supported;
- rename and delete;
- show safe capture timestamp / manufacturer / model / Android / API context;
- keep built-in validated reference profiles clearly separate from personal profiles;
- design and validate the persisted schema before storage/UI implementation;
- do not silently persist the transient v2.1 session profile.

Never persist or expose:

- raw ADB serial;
- durable device-correlation identifiers/hashes;
- Android ID;
- GSF device ID;
- IMEI/MEID;
- SIM/subscriber identifiers;
- Google identity;
- OAuth/AAS/Play bearer tokens;
- cookies;
- Google check-in ID;
- profile hashes derived from sensitive identifiers.

Raw public Store evidence remains authoritative. Device Specific evidence is additive.

The focused #200 development implementation uses `personal_device_profiles.json` schema v1 in the active application-data directory. Each complete saved profile has a random `personal:` UUID4 record ID, a random UUID4 cache revision, local name, UTC capture/update times, safe manufacturer/model/Android/API context and only the allowlisted resolver mapping. Explicit Save Locally follows the existing transient Get Phone Data capture. Saved profiles work without ADB and are visually separated from built-in validated references and `connected_device` session capture. Rename leaves cache identity stable; confirmed refresh rotates the random revision and blocks obvious manufacturer/model mismatch, while explaining that matching context cannot prove device identity. Delete falls back to the built-in default. Reset Settings retains the separate library but resets selection; cache/history maintenance retains it. There is no v2.1 transient migration. PR #215 is merged and its exact-main Quality gate passed.

Advanced Settings preserves a configured `personal:` selection as an unavailable placeholder if this build cannot load its library or selected record. Unrelated settings saves retain that ID without touching future-schema bytes; explicit built-in selection and Reset All may replace it.

### 3. CLI/headless auditing — #211

The merged #211 implementation contains the separate `playstore-app-audit-cli audit` command for App List, explicit local package files, recursive Local APK folders and connected-phone ScanSession. It replaces the legacy positional `cli.py` behavior, keeps the GUI installed command unchanged and does not bump the application version. Canonical services handle Store lookup/fallback, local package fan-out, Device Specific/Alternative Distribution, classification/scoring and JSON/CSV export. CLI overrides do not persist settings or history. PR #216 and post-merge Quality #607 complete this implementation pillar.

The merged implementation makes normal standalone packages invoke the CLI as `PlayStoreAppAudit[.exe] cli audit ...` on Windows/Linux or `PlayStoreAppAudit.app/Contents/MacOS/PlayStoreAppAudit cli audit ...` on macOS; default invocation remains GUI. Expired or unavailable inherited Device Specific settings do not block public Store evidence, while explicit CLI overrides are checked before audit.

Add a scriptable non-GUI entry point that reuses existing domain/service logic.

Direction:

- support App List files and Local APK files/folders end-to-end without opening the Qt UI;
- include connected-phone/read-only ADB support in v2.2, either in the main CLI issue or a focused follow-up before release freeze;
- reuse canonical Store, Local APK, Device Specific, cache, scoring and export semantics;
- provide versioned JSON and canonical CSV where applicable;
- use deterministic non-zero exit codes for invalid input, failed audit and interruption;
- handle Ctrl+C cooperatively;
- do not drive Qt widgets or create a parallel Store/ADB implementation;
- no interactive TUI, daemon/server mode, scheduled monitoring or self-update work.

## Deferred / later 2.x

Keep these outside v2.2 unless a deliberate roadmap decision changes scope:

- `#147`: arbitrary named Custom Views beyond the two v2.2 source-family layouts;
- `#154`: production signing / notarization trust;
- `#209`: verified update download and eventual safe self-update architecture;
- duplicate APK detection/management;
- custom commands/integrations;
- Windows Explorer integration;
- broad dashboard redesign;
- watchlists/background monitoring.

## Product / engineering invariants

Preserve:

- exact-SHA release discipline;
- published release immutability;
- normal merge commits, no squash/rebase;
- `main` as the only permanent branch;
- cheap Quality checks on normal feature PRs;
- expensive package builds only at deliberate evidence gates;
- read-only ADB with respect to installed apps;
- conservative Store availability/version semantics;
- raw public Store result as authoritative evidence;
- privacy rules for connected-device and Device Specific data;
- Qt Widgets/platform-default style;
- the established technical slug/repository/executable naming `PlayStoreAppAudit`; no v2.2 naming migration is planned.

## Active release preparation

Final pre-release freshness is active from exact main `486ef062548cab2dee5960c38f02dbfbca226640`, the normal merge of PR #219, with post-merge Quality #628 / `36938816496` successful. All three v2.2 product pillars are complete (#214/#208, #215/#200, #216/#211). Entry freshness passed through PR #217, merge `aea0382802edb27237fa25950e01b75c0ef4ad36`, followed by Quality #618 / `36870324623`; Sponsors PR #218 merged at `fd104c13bcaf2ff4af4b3a3746f87044554b9fa0`, followed by Quality #620 / `36875676207`.

Canonical source/package version is **2.2.0** (Windows File/Product **2.2.0.0**). Linux release builds use Ubuntu **24.04 for x64 and ARM64**, with full packaged ELF inspection and deliberate Ubuntu 22.04 x64 runtime smoke. macOS remains macOS 26 / Xcode 26.6 on both architectures; Xcode 27 preview is excluded. Six targets and the eight-file public asset set remain required. Production signing/notarization stays outside scope under #154.

The [release-preparation record](V2_2_RELEASE_PREP.md) and [draft release body](V2_2_RELEASE_BODY_DRAFT.md) record preparation merged through [PR #219](https://github.com/mrc-labs/PlayStoreAppAudit/pull/219). Linux diagnostic #13 / `36930784495` passed both architectures at `fbc19d0de4774b6ab83aff6ed709b965bcd9c47a`, observed Python 3.14.8: x64's tested Ubuntu 22.04 GUI/CLI paths passed after ABI remediation (maximum GLIBC 2.35 / GLIBCXX 3.4.29); native ARM64 retained its 24.04 target (2.38 / 3.4.32). These are prep diagnostics, not final candidates; the record preserves the failed intermediate evidence and ARM64 retry observation. Post-merge Quality #628 passed at the exact preparation merge SHA `486ef062548cab2dee5960c38f02dbfbca226640`.

The [final pre-release freshness gate](V2_2_FINAL_PRE_RELEASE_FRESHNESS.md) is **PASSED** on `v2/final-freshness-2.2.0` in [draft PR #220](https://github.com/mrc-labs/PlayStoreAppAudit/pull/220), which remains open/unmerged for control-tower review. Exact Python **3.14.8** is pinned and checked in all 11 workflow setup environments; Ruff **0.16.10**, mypy **2.4.0**, Rust **1.99.0** and current Ubuntu vendor OpenSSL security packages are validated. Affected Linux x64/ARM64, Windows ARM64 and macOS Intel diagnostics passed; final documentation-head Quality evidence is recorded in the PR before handoff. Normal merge and post-merge Quality remain prerequisites to release-SHA selection. After permanent v2.2 closure restore rolling development Python tracking as documented in the final record. Release SHA freeze, final six-platform candidates, assembly, tag, publication and public re-download verification remain **pending**. No release SHA is frozen; #212 remains open; #147/#154/#209 remain outside scope.

## Continuation

Use this file as the current handoff for v2.2 work. The handoff export script discovers the newest versioned `docs/HANDOFF_V*.md`, so after this file lands it should select `HANDOFF_V2.2.md`.

Generate future chat handoff exports only from a clean synchronized checkout, following `docs/RELEASE_CLOSURE.md` and the repository's normal synchronization rules.
