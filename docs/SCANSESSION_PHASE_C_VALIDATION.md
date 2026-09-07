# ScanSession Phase C validation — local source work

Date: 2026-09-07. Application: 1.99.0. Verdict: **READY FOR RC6 BUILD**.

The implementation, final source-validation gate and five real-device iterations after priming pass. The user confirmed that they replaced the **Pixel 10 Pro with 329 apps** with the currently connected **Pixel 11 Pro with 315 third-party apps**. This is the available reference for Phase C. Current within-device measurements prove command reuse and Run savings; cross-device historical timing deltas are observational and cannot be attributed solely to software. The requested original 329-app measurement is unavailable following the device replacement; its historical results remain clearly identified. RC6 packaging belongs to the next session.

## Preflight and delivery boundary

| Check | Verified state |
| --- | --- |
| Repository workspace | `C:\Users\mauro\Progetti\git\PlayStoreAppAudit` |
| Branch | `prototype/v1.99-native-actions` |
| Starting HEAD / Phase C commit parent | `f7d100d67697b947bea6f6dec7206516e0a41276` |
| Parent | `b2cd5ff35da874f2d228dfe89851df93528a5155` |
| Subject | `feat: capture compact metadata during phone scan` |
| Git author/committer identity | `MRC <164878571+mrc-labs@users.noreply.github.com>` |
| Version | `1.99.0` in package and project metadata |
| Initial tracked tree | Clean |
| Upstream / matching remote-tracking branch | None; inspected local configuration/references only |
| Remote activity | None: no fetch, pull, push, PR, GitHub call or remote mutation |
| Packaging | No Nuitka, `build_windows_exe.bat`, RC6 EXE/ZIP or release artifact |
| Phase C commit | One local commit `feat: add optional full scan enrichment`; this report is included in that candidate commit, whose exact SHA is recorded in the final session response |
| Final working state | Verify clean tracked tree after the local commit; ignored local evidence remains outside it |

## Feature and architecture acceptance

| Requirement | Implementation and evidence |
| --- | --- |
| Setting | `collect_full_device_metadata_on_scan`; a global native checkbox under Tools > Advanced Settings > Device |
| Exact label | Collect full device metadata during Scan Phone |
| Copy | “Captures extended installed-app metadata during Scan Phone so it remains available if the device is disconnected before the audit. This can significantly increase scan time.” |
| Default/migration | OFF on fresh install, missing key or malformed value. Only boolean `true` enables it; save/load preserve ON/OFF. Reset chooses OFF; Cancel does not save. |
| Preference isolation | Outside Column Presets, Custom View, Audit Presets, filters and exports. Existing connected-device metadata preference continues to govern deferred T2; completed captured evidence remains reusable. |
| Standard OFF | Original compact T1 collection only, with unchanged package/disabled aggregate commands. No full collector, dumpsys, rich versionName, SDK, timestamps or permissions during Standard Scan. |
| Advanced ON | Compact capture first, then exactly one invocation of `collect_device_metadata_v9` with the exact session context. No second full collector. |
| Typed full state | `FullMetadataStatus.NOT_REQUESTED`, `.INCOMPLETE`, `.COMPLETE`; frozen/slotted `FullPackageMetadata` parsed field tuples; successful timestamp and captured permissions flag on the same immutable ScanSession. |
| Completion proof | A fresh `FullCollectionReceipt` remains false until collection finishes with valid context, all requested packages, numeric versionCode/target/min SDK inputs and no cancellation. Optional versionName/timestamps may be absent on a device. Nonempty or partial dictionaries are insufficient. |
| Collector reuse | Existing bulk parser and per-package compatibility fallback remain. Missing/incomplete bulk blocks can recover through that fallback. The old v9 cross-module installer wrapper is removed; the production collector supplies structured installer fields locally. Existing startup diagnostics forward the new keywords. |
| Complete full Scan | Retains existing rich fields. Subsequent Run uses the immutable parsed snapshot and does not discover or query a device. New Scan Phone explicitly captures newer state. |
| Failed/incomplete full Scan | Discards all partial rich fields, keeps the compact session, and shows “Phone scan ready with compact metadata. Extended metadata could not be captured.” Run remains enabled. |
| Failed Scan + connected Run | Normal T2 enrichment runs only for the matching authorized phone; no partial rich T1/T2 blend is retained. |
| Failed Scan + disconnected Run | Store work proceeds with compact T1 only; rich-only values remain unavailable. |
| Complete Scan + connected/disconnected Run | Deterministic tests verify the same rich results and zero additional collection in both cases. |
| Rich fields | Installed versionName/versionCode, installer package/source/category, enabled state, target/min SDK, first-install/local-update time, Compatibility and configured sensitive-permission fields. Compact system classification remains attached. |
| Installed vs Store | Existing versionName comparison unchanged. Full capture supports Match/Different normally offline; Standard disconnected remains Unknown. |
| Android Compatibility | Existing target/device SDK classifier unchanged and available from captured full fields; Standard disconnected does not invent SDK inputs. |
| Permissions | Existing `permissions_audit_enabled` alone determines capture. OFF yields no permission details; ON retains them after disconnect. No second preference. |
| T1 inventory | Compact package set/versionCode/installer/enabled/system remain authoritative even when a full dump contains later/different values. Rich versionName does not overwrite compact inventory semantics. |
| Baseline promotion | Scanning does not create a persistent inventory baseline. Completed successful audit promotes compact T1; stopped/failed audits do not. |
| Source isolation | Complete phone A data cannot bleed into phone B or a file; file transitions clear the selected session. Recent Sources use the existing file/source loading routes. New sessions replace old ones. |
| Stale completion | Request-generation checks reject late complete results; tests also hold a real worker in slow full collection while newer phone/file/close actions invalidate it. |
| Responsiveness/close | Qt continues dispatching events while the worker is blocked. Per-request cooperative cancellation prevents new collector commands and suppresses late selection. In-flight commands drain under existing timeouts; no forced thread/process termination. |

## Command accounting and retained probes

Historical columns are the user-supplied accepted measurements. Phase C command counts were observed in every one of five measured iterations on the Pixel 11 Pro/315-app device. The Standard/Advanced totals include one successful executable discovery. No locale, incomplete-context or per-package fallback occurred; those compatibility paths can add commands on other devices.

| Command category | RC5 Scan | Phase A Scan | Phase B/C Standard | Historical full envelope | C Standard T2 | C Advanced additional | C Advanced total | Run after complete Advanced |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `adb version` | 3 | 1 | 1 | 1 | 1 | 0 | 1 | 0 |
| `adb devices` | 2 | 1 | 1 | 1 | 1 | 1 | 2 | 0 |
| `shell getprop` | 2 | 1 | 1 | 1 | 1 | 0 | 1 | 0 |
| `get-serialno` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Plain package enumeration | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Compact package/installer/versionCode enumeration | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| Disabled packages | 0 | 0 | 1 | 1 | 1 | 0 | 1 | 0 |
| Separate installer list | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| Bulk `dumpsys package` | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 0 |
| **Total** | **9** | **4** | **5** | **6** | **6** | **2** | **7** | **0** |

Advanced reuses the validated executable and captured Android API instead of repeating executable discovery/getprop. It reuses the compact installer map and disabled state instead of repeating `pm -i`/`pm -d`. Device identity comes from the hashed/masked session; no `get-serialno` is needed. One new `devices` query deliberately remains at the compact-to-full boundary: it verifies single-device authorization and the session hash and supplies a command-local selector for every full command. A replacement/disconnected phone cannot silently supply full data. Missing compact/API inputs fall back to the established aggregate queries with that same selector.

Standard T2 must revalidate the executable and current phone because time may have elapsed since Scan. Its one exact authorization/hash check replaces Phase B's immediately preceding generic authorization query; there is no duplicate generic check. Standard T2 continues to refresh getprop/disabled/installer/dump data at T2. All-package Scan retains its separate system classifier; missing locale retains its read-only locale fallback.

Observed supported-path launch reductions are:

- Original Scan 9 → 5: **4 fewer, 44.4%**.
- Historical full envelope 6 → 2 additional Advanced commands: **4 fewer, 66.7%**.
- Within that full envelope, discovery/context version/devices/getprop 3 → 1: **2 fewer, 66.7%**; two more saved commands come from reusing installer/disabled inputs.
- Original Scan + full approximately 15 → Advanced 7: **8 fewer, approximately 53.3%**.
- Complete Advanced Scan invokes the full collector **1 time**; the following Run invokes it **0 additional times**, with **0 dumpsys** and **0 rich-metadata ADB launches**. All five physical-device iterations, connected/disconnected fixtures and the real Qt event-loop smoke prove these counts.

## Required performance matrix

Historical scenarios use the Pixel 10 Pro/329-app scope; all current scenarios use the Pixel 11 Pro/315-app scope (14 fewer apps, 4.3%). Each current distribution contains five measured iterations after untimed Standard/T2 and Advanced/reuse priming. Device permissions capture was OFF for timing, with ON/OFF behavior verified separately in deterministic acceptance. Current Standard and Advanced scenarios alternated within each iteration; conditions were not altered to favor either path.

| Scenario | Min s | Median s | Mean s | Max s | ADB launches | Packages |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| A. Original RC5 Scan | 0.673 | 0.687 | 0.691 | 0.717 | 9 historical | 329 |
| B. Phase A Scan | 0.469 | 0.532 | 0.541 | 0.663 | 4 historical | 329 |
| C. Phase B Compact Scan | 0.633 | 0.699 | 0.687 | 0.734 | 5 historical | 329 |
| Historical deferred full enrichment | 7.169 | 7.964 | 7.811 | 8.073 | 6 historical | 329 |
| Historical Scan + full | — | 8.639 | — | — | approximately 15 | 329 |
| D. Phase C Standard Scan | 0.543 | 0.617 | 0.601 | 0.661 | 5 | 315 |
| C Standard T2 full enrichment | 4.571 | 4.695 | 4.727 | 5.079 | 6 | 315 |
| E. Phase C Standard Scan + T2 | 5.120 | 5.238 | 5.328 | 5.740 | 11 | 315 |
| F. Phase C Advanced Full Scan | 4.634 | 4.917 | 4.847 | 5.076 | 7 | 315 |
| Advanced full-collector subphase | 4.074 | 4.318 | 4.273 | 4.488 | 2 additional | 315 |
| Run device preparation/reuse | 0.001885 | 0.002161 | 0.002291 | 0.002737 | 0 | 315 |

Historical dumpsys cost was approximately **6.4–7.4 s / 12.6 MB** on the Pixel 10 Pro. Current measurements:

| Full iteration | Standard T2 dumpsys s | Advanced dumpsys s | Advanced output bytes (UTF-8 encoded captured text) |
| --- | ---: | ---: | ---: |
| 1 | 4.030271 | 4.190287 | 12,422,259 |
| 2 | 3.964030 | 3.915756 | 12,422,272 |
| 3 | 3.976209 | 4.256901 | 12,422,272 |
| 4 | 4.351800 | 3.906344 | 12,422,233 |
| 5 | 3.912152 | 4.080314 | 12,422,432 |
| **Min / median / mean / max** | **3.912 / 3.976 / 4.047 / 4.352** | **3.906 / 4.080 / 4.070 / 4.257** | **approximately 12.42 MB** |

Dumpsys was materially shorter on the current device than the historical reference, but this is a changed-device measurement, not evidence that the implementation accelerates dumpsys. Its command and parser are unchanged. Within the same current device, Advanced dumpsys median was actually 0.104 s longer than Standard T2; the improvement surrounding it comes from context reuse. The ratio of Advanced dumpsys median to Advanced total median is **83.0%**.

| Median comparison | Delta seconds (new minus reference) | Delta percent | Interpretation |
| --- | ---: | ---: | --- |
| C Standard vs RC5 Scan | -0.069979 | -10.19% | Changed device/app count |
| C Standard vs Phase A | +0.085021 | +15.98% | Changed device/app count; C includes compact metadata |
| C Standard vs Phase B | -0.081979 | -11.73% | Changed device/app count |
| C Standard T2 vs historical 7.964 s | -3.269325 | -41.05% | Changed device/app count; standalone full commands unchanged |
| C Advanced vs historical 8.639 s Scan + full | -3.722164 | -43.09% | Changed device/app count plus context reuse |
| C Advanced collector vs historical 7.964 s | -3.645511 | -45.78% | Changed device/app count plus context reuse |
| C Advanced vs current Standard + T2 | -0.321173 | -6.13% | Same device and 315-app scope |
| C Advanced collector vs current Standard T2 | -0.376185 | -8.01% | Same device and 315-app scope; envelope includes fresh T2 discovery |

The benchmark uses the real Scan UI path and real Run metadata worker with synthetic already-cached Store rows, excluding Store/network latency. Providers/history/icons are disabled in an isolated data directory. It records only sanitized command categories/times/output lengths; neither raw serials nor raw dump bodies are written. Local detailed evidence is ignored at `artifact/phase-c/benchmark-results.json`.

To check Standard regression independently of the hardware change, the exact committed Phase B source at `f7d100d67697b947bea6f6dec7206516e0a41276` was extracted locally into ignored evidence and compared with current source on the same Pixel 11 Pro/315-app scope. Five iterations after separate priming gave Phase B min/median/mean/max **0.533 / 0.634 / 0.679 / 0.980 s** and Phase C **0.517 / 0.613 / 0.635 / 0.749 s**, with exactly five ADB launches and no dumpsys in every iteration. The median delta is **-0.021 s / -3.3%**: no material Standard regression is observed. These small samples establish equivalence within observed variability, not a precise software speedup. Permissions were OFF and system apps excluded in both the current and historical benchmark settings. The accepted historical 329-app Phase B measurements above are preserved.

Run after Advanced has **2.161 ms median** device preparation/row merging overhead. The immutable snapshot copy alone is **0.1647 ms median** (min/mean/max 0.1341/0.1640/0.1929 ms). Advanced total plus the following Run metadata preparation is **4.918954 s median**. Compared with performing current Standard T2 again, reuse saves **4.692514 s** at the median and all six fresh-T2 commands. The full collector is paid once in Scan, with no additional collector, dumpsys or metadata ADB command in Run.

### Performance attribution and explicit answers

1. **Basic loading vs RC5:** Phase C measures **0.070 s / 10.2% faster**, subject to the device/scope difference. Historically Phase A alone saved **0.155 s / 22.6%** at the median by removing repeated discovery/context work.
2. **Compact metadata cost:** the accepted same-reference-device Phase B comparison adds **0.167 s / 31.4%** over Phase A and one aggregate command. Phase C is 0.085 s / 16.0% above the historical Phase A figure on the new phone; that cross-device delta does not isolate compact cost.
3. **Full loading now:** Advanced is **3.722 s / 43.1% below** the old 8.639 s total, including the faster current phone. The fair current-device comparison is **0.321 s / 6.1% below** Standard Scan + T2. Advanced collector vs current T2 saves **0.376 s / 8.0%** at the median despite a slightly longer Advanced dump.
4. **Full-path launches:** approximately **15 → 7**, eight removed; the full envelope is **6 → 2**, four removed. All five current iterations confirm counts. Comparing paired surrounding ADB command durations gives **0.503 s median** saved; comparing paired collector/envelope time after subtracting dumpsys gives **0.480 s median** saved. Those current-device measurements isolate surrounding work much more directly than the historical total delta.
5. **Run reuse saving:** **4.692514 s** against fresh current T2, with **2.161 ms** reuse overhead and zero extra device commands. Historical 7.964 s is not substituted as a new saving measurement.
6. **Remaining intrinsic cost:** Advanced dumpsys median is **4.080 s**, approximately **83.0%** of Advanced total median. Its changed-device reduction must not be credited to context deduplication.

## Final source-validation evidence

| Gate | Result |
| --- | --- |
| Python 3.13 | **3.13.15 x64**, MSC v.1944 AMD64; PySide6 **6.11.1** |
| Python 3.13 full pytest | **699 passed in 23.51 s** |
| Python 3.14 | **3.14.6 x64**, MSC v.1944 AMD64; PySide6 **6.11.2** |
| Python 3.14 full pytest | **699 passed in 22.74 s** |
| New focused Phase C suite | **49 passed** |
| Existing regression suite | All **650** pre-Phase-C tests retained and passing |
| Application compileall | PASS on both interpreters |
| Quality helper compilation | PASS on both; all six workflow-listed helper modules |
| Full Ruff | `python -m ruff check .` PASS on both interpreters |
| Dependency consistency | `pip check` PASS on both interpreters |
| PowerShell helper syntax | PASS for `scripts/export_chat_handoff.ps1` |
| Qt source/offscreen smoke | PASS on both; canonical Quality assertions included |
| Native Advanced Settings visual check | PASS: Windows `windows11` platform QStyle, Segoe UI, real 175% scaling; new checkbox/copy fit the existing Device page |
| Same-device Standard regression comparison | PASS: exact committed Phase B vs current C, five iterations each on Pixel 11 Pro/315 apps; 0.634 vs 0.613 s median, five launches each |
| Event-loop/fake-device smoke | PASS on both: full Scan, disconnect, fully cached Run, rich fields retained, reusable idle; six service commands during Scan (discovery stubbed), zero during Run |
| Diff whitespace check | PASS |

Quality requires Python 3.13 and 3.14 with Qt 6.11+; the installed secondary environment's Qt 6.11.2 is reported explicitly. Production pins, release baseline and application version are unchanged. No dependency download or installation occurred.

Full regression coverage includes pristine Basic/Custom availability and persistence, Column Presets, semantic widths/wrapped headers, compact status bar, menus/Details modes, execution-only Audit Presets, absent SDK Maintenance Filter, Clear All Filters, Device History, Run/Pause/Resume/Stop, cached completion, Maintenance Score, F-Droid/Aptoide and provider-disabled cleanup, CSV/JSON/HTML exports, source/device isolation, Phase A command reuse and Phase B compact/disconnected/T1 inventory behavior. Native packaged RC6 acceptance is explicitly outside this source gate.

## Privacy, complete-diff review and changed files

ScanSession and its immutable full tuples remain process/window-local; only parsed existing fields are retained. Raw serials are used transiently for command selection and reduced to the existing hashed/masked identity for the session. Raw dumpsys output remains transient in the collector and is never persisted. No Scan operation creates history, inventory or Store/provider cache entries. The new preference is a boolean without sensitive content. No credentials, full-session schema or raw dump enter new settings/logs/exports. Existing export schema, scoring/provider policy and Store cache code are unchanged.

Reviewed source changes:

- `playstore_app_audit/services/scan_session.py`: immutable full state/capture and ephemeral matching-device selector.
- `playstore_app_audit/services/device_insights.py`: one existing collector with optional context, explicit receipt and local installer fields.
- `playstore_app_audit/services/installer_source.py`: remove the obsolete production v9 collector wrapper.
- `playstore_app_audit/services/performance_diagnostics.py`: forward optional collector arguments through existing diagnostics.
- `playstore_app_audit/services/state.py`: strict default/save/load handling for the new preference.
- `playstore_app_audit/ui/audit_window.py`: background opt-in capture, per-request cancellation and partial-success feedback.
- `playstore_app_audit/ui/device_window.py`: complete-session Run reuse and one exact Standard T2 device check.
- `playstore_app_audit/ui/insights_window.py`: preserve partial-success status text.
- `playstore_app_audit/ui/preferences_window.py`: native Device checkbox/copy/save/reset.
- `tests/test_scan_session_phase_c.py`: 49 new regression cases.
- `tests/test_scan_session_ui.py`: retain off-thread assertion with the extended worker arguments and uncancelled event.
- `README.md`, `docs/PROJECT_DECISIONS.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, `docs/HANDOFF_V1.99.md` and this report: current behavior, validation, remaining gate and local-only continuation.

Temporary benchmark and smoke instrumentation is ignored under `artifact/phase-c/`, outside production behavior and outside the intended commit. Historical release/changelog documentation, repository remotes, version, dependencies and packaging workflows are untouched.

## Candidate closure and next session

The user confirmed the phone replacement and smaller app inventory; Phase C uses the measured Pixel 11 Pro reference with the limitations above. The full source gate, native Device settings layout, five-iteration performance evidence and complete diff were reviewed. The sole authorized local MRC commit is `feat: add optional full scan enrichment`, with parent `f7d100d67697b947bea6f6dec7206516e0a41276`. Verify its clean tracked tree, branch/version and absence of upstream/matching remote-tracking branch after commit. This is the RC6 **source** candidate, not an RC6 packaged or user-accepted binary.

The next session may perform separately authorized RC6 packaging and acceptance. Any subsequent source/tooling change invalidates the source candidate and requires appropriate revalidation. This session does not push, invoke Nuitka or create an RC6 package.

**READY FOR RC6 BUILD — source gate and current-device performance acceptance passed; historical timing comparisons explicitly include the confirmed device change.**
