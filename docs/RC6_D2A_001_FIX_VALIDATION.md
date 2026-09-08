# RC6-D2A-001 source correction

Date: 2026-09-08. Version: **1.99.0**. Verdict: **READY FOR RC7 BUILD**.

RC6 **failed D2A** because its Device changes header lagged one completed audit.
RC6 must not be reused for acceptance or release. The next package is **RC7**;
this session produces its source candidate only. No D2A continuation, D2B,
Nuitka, package build, real-device command or remote activity occurred.

## Starting state and preserved evidence

- Branch: `prototype/v1.99-native-actions`, no upstream or matching local remote-tracking ref.
- Exact parent: `572be8edf4689cacbe23084d7602e0b71e7ed8df`.
- Parent subject: `feat: add optional full scan enrichment`.
- Initial tracked tree/index clean; package/project version `1.99.0`.
- Author and committer: `MRC <164878571+mrc-labs@users.noreply.github.com>`.
- Configured repository: `mrc-labs/PlayStoreAppAudit`; only local configuration
  and refs inspected. No fetch or live remote-branch verification.
- Read `artifact/rc6-evidence/d2a/REPORT.md`, `DEFECT-RC6-D2A-001.md`, installer
  N/N+1 native records, stale-count UIA/screenshot, Phase C validation and handoff.
- RC6 ZIP and RC6-labelled copy SHA-256:
  `5de3e429cf2f6a25fc5f4ffad334a0d5f1735ea6c061a175ca32db9373c98044`.
- RC6 EXE SHA-256:
  `639dddc3cfb4af23346e4aba9a271bcdabe0b4ce214573afb5e10e62a786cd5a`.
- RC6 artifacts and evidence are preserved. New local validation outputs live
  separately in ignored `artifact/rc7-source-fix/`.

## Exact cause and state trace

This is a presentation/state-ordering defect, not an inventory algorithm defect.
The pre-fix Qt regression reproduced `[False, True]` for presence of the header
count in installer-change N / unchanged N+1, where `[True, False]` was required.
Both Details assertions passed before the header assertion failed. The initial
11-case regression run had 10 failures and one passing no-change case. A later
new-Run test separately reproduced retained header text after rows were cleared.

| State/value | Ownership and use |
| --- | --- |
| `_scan_session` | Selected immutable T1 snapshot; a later Scan may replace selection but does not compare/promote inventory. |
| `AuditRunResult.session`, `_audit_session`, `_finalizing_session` | Existing audit-generation guards before queued completion and before result installation/promotion. |
| `result.metadata['scan_session']` / `source_scan_session` | Exact session bound to the audit; promotion derives `inventory_device_summary` and `t1_inventory_rows` from it, not a newer selection. |
| `inventory_path(device_id)` / `previous`, `old_apps` | Persisted previous successful coherent inventory; comparison reads this before writing the current baseline. |
| `current_source`, `current` | Current T1 package/versionCode/installer/enabled/system inventory, from `scan_session.inventory_rows`. Rich T2 fields do not redefine it. |
| `changes[package]`, `counts`, `removed` | One service comparison; taxonomy precedence is new, version, installer, state, same; removed packages are counted separately. One classification per present package. |
| `result.rows`, `typed_rows`, `current_rows`, model rows | Current result collection installed by completion; promotion annotates `row['device_change']`, then replaces model rows again. |
| `_last_inventory_changes` | Returned comparison aggregate (`counts`, `removed`, `had_previous`); previously retained the preceding audit during initial summary refresh. No second stored header counter exists. |
| `_device_inventory_had_previous` | Row flag set by `_sync_post_audit_views` from the same aggregate. |
| `device_inventory_line`, `details_panel.device_label` | Details interprets `device_change` and the history flag as Installer/source changed, No inventory change, etc. |
| `summary.device_change_count`, `concise_summary`, `summary_label` | Header sums existing new/removed/version/installer/state counts only when `had_previous`; text is omitted for zero or empty results. QLabel text was the stale presentation cache. |
| `_merge_base_rows`, `_v9_targeted_active`, metadata `targeted` | Existing targeted Store recheck retains inventory and merges rows; no new inventory comparison/promotion. |

Other summary overrides supply ordinary status/filter presentation; the final
`ResultsWindow._update_summary` supplies the Device changes suffix. Change
Overview and Device Inventory Changes consume the existing aggregate too.
File loading and Clear Device Inventory History already reset it. Clear Results
empties rows and hides the suffix under existing rules.

## Old and corrected completed-audit timeline

Old ordering:

1. Run clears result rows; old aggregate/header text can remain.
2. Worker returns a generation-bound result; MainWindow schedules existing Qt finalization.
3. Completion installs current rows; inherited completion refreshes the summary
   using the previous `_last_inventory_changes`.
4. Initial post-audit view synchronization refreshes Details/actions.
5. Only after successful finalization, history persistence runs when enabled;
   inventory comparison reads old baseline, annotates current rows, writes T1,
   returns the current aggregate, and reinstalls model rows.
6. Post-promotion synchronization refreshes Details/overview/actions, **omitting
   the summary**. Idle retains the previous generation's count.

Corrected ordering retains those existing lifecycle and persistence boundaries:

1. An accepted new full Run clears the old aggregate and refreshes the empty summary.
   Pause/Resume and rejected starts do not take this branch.
2. After both existing generation guards, full result replacement discards the
   prior aggregate before inherited finalization. This also covers stopped/failed
   completion. Targeted merged Store rechecks retain their existing inventory.
3. Successful finalization performs the same single comparison and promotion as before.
4. `_sync_post_audit_views` now refreshes the summary together with Details and
   overview from the newly installed aggregate/annotated rows, before returning idle.

The authoritative count remains `summary.device_change_count(_last_inventory_changes)`.
The saved baseline is never reread/recompared to calculate the completed header.
Thus a real change stays visible even though its T1 snapshot is now the baseline
for the next successful audit. There is no new timer, signal, counter, comparison,
repaint workaround or generation identity. Scan alone, Stop and failure never promote.

## Regression evidence

The new `tests/test_device_change_summary_ui.py` has **12 deterministic cases**.
It uses real inventory persistence in temporary directories and the production
queued Qt completion path; no sleep or external service/device is required.

| Sequence | Result |
| --- | --- |
| A / A | Details No inventory change; zero suffix omitted. |
| A / B installer | Visible Details Installer/source changed; visible header Device changes 1 in N. |
| B / B next run | Visible Details No inventory change; Device changes suffix omitted in N+1. |
| Version change | Installed version changed; same-run count 1. |
| Added package | Newly installed; same-run count 1. |
| Removed package | Same-run count 1 and removed-package overview; remaining row says No inventory change. Removed packages have no current Details row under existing semantics. |
| Installer plus added | Existing per-package classification totals 2; header 2, corresponding Details labels. |
| Stopped / failed | Baseline bytes unchanged; no previous completed count or current-comparison Details; next success compares against the prior successful baseline and displays 1. |
| Clear Results / next success | Empty results hide suffix; unchanged next run does not resurrect 1. |
| New Run before completion | Rows empty and previous count gone immediately; baseline unchanged. |
| Stale/duplicate finalization callback and later Scan | Prior-generation callback and already-finalized deferred callback cannot replace the current header/baseline; Scan does not promote. |
| Different selected session during finalization | Completed header and persisted T1 use the session bound in the result. |

Focused suite: **121 passed**, covering new header tests plus audit finalization,
cooperative lifecycle and ScanSession A/B/C/UI. Full suites retain all 699 prior
tests plus these 12. Coverage includes default-OFF Advanced full Scan, full capture
and disconnected reuse, compact snapshot, T1 vs T2, collector command accounting,
successful-only promotion, Device History, Details, status/header, Clear Results,
Run/Pause/Resume/Stop, Maintenance Score, providers, exports, Custom/presets/menus.

## Source gate and scope review

| Gate | Python 3.13.15 x64 / PySide6 6.11.1 | Python 3.14.6 x64 / PySide6 6.11.2 |
| --- | --- | --- |
| Full pytest | 711 passed, 26.62 s | 711 passed, 26.04 s |
| compileall / Quality helper compilation | PASS | PASS |
| Repository-wide Ruff | PASS | PASS |
| pip check | PASS | PASS |
| Canonical Qt assertions / source offscreen smoke | PASS | PASS |
| Full Scan / disconnect / cached Run event-loop smoke | PASS | PASS |

The retained source smoke uses a fake phone and confirms six service commands
during full Scan with discovery stubbed, and zero additional Run commands.
PowerShell helper syntax and `git diff --check` also pass. No dependencies were
installed or downloaded. No real-device benchmark or broad UX acceptance was run.

Production changes are ten added lines across `ui/main_window.py` and
`ui/results_window.py`. No ADB commands, dumpsys, discovery or Store requests were
added. No ScanSession redesign, inventory taxonomy, baseline algorithm, scoring,
provider/export policy, version, dependency, builder/tooling, privacy field or
remote configuration change. RC6 evidence is not edited to reflect this fix.

One local commit is authorized: `fix: synchronize device change count`, with the
exact parent above. Its SHA is recorded in the final session report; verify a clean
tree/index and no upstream after committing. That commit is the **RC7 SOURCE
CANDIDATE**, not a packaged or acceptance-approved RC7. Packaging belongs to the
next separately authorized session.
