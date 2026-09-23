# Store App Audit v2.2 Development Handoff

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

The application version remains `2.1.0` until a deliberate v2.2 release-preparation/version-bump step.

## v2.2 approved product pillars

v2.2 has three approved pillars. Do not silently add unrelated deferred work to the release.

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

The first implementation PR of v2.2 should start with step 1, not with broad UI redesign.

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

### 3. CLI/headless auditing — #211

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

## Immediate next implementation

Start with issue `#208`, source-family Custom persistence foundation.

Before editing:

1. synchronize a clean normal checkout to current `origin/main`;
2. verify no user work is dirty;
3. create a short-lived feature branch;
4. inspect `playstore_app_audit/ui/column_presets.py`, `compact_window.py`, `main_window.py`, state/settings normalization and existing preset tests;
5. implement the smallest durable settings/migration layer for the two source-family Custom layouts;
6. add focused migration/restart/source-switch tests;
7. do not mix #200 or #211 implementation into that first PR.

## Continuation

Use this file as the current handoff for v2.2 work. The handoff export script discovers the newest versioned `docs/HANDOFF_V*.md`, so after this file lands it should select `HANDOFF_V2.2.md`.

Generate future chat handoff exports only from a clean synchronized checkout, following `docs/RELEASE_CLOSURE.md` and the repository's normal synchronization rules.
