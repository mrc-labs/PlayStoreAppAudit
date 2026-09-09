# RC7 HTML Device Inventory Change export correction

Date: 2026-09-09. Version: **1.99.0**. Verdict: **READY FOR RC8 BUILD**.

RC7 passed D1, D2A and D2B1, then **failed final packaged acceptance** because
the HTML export omitted Device Inventory Change while CSV and JSON preserved it.
RC7 must not be reused. Its ZIP, extracted executable and all records under
`artifact/rc7-evidence/` remain historical evidence and were not rewritten.

## Starting state and reproduction

- Branch: `prototype/v1.99-native-actions`; no upstream.
- Exact parent: `6a0c96b7d355278813038207502be39cad350b49`.
- Parent subject: `fix: synchronize device change count`.
- Initial tracked worktree/index clean; application/project version `1.99.0`.
- Author and committer identity: `MRC <164878571+mrc-labs@users.noreply.github.com>`.
- RC7 ZIP SHA-256:
  `3b23837de0948736e9d3ca0706e432989c3da6e66f6a8927bff6f515d8843d71`.
- RC7 EXE SHA-256:
  `00c6cc818a856bb652cc27beec131dbbb1d2ab7226d5a1904cca26e49bec2741`.
- The preserved packaged HTML contains all six expected packages, Maintenance
  Score and provider evidence, but no Device Inventory Change header or value.
  Its paired CSV/JSON files both contain `device_change = Installer changed`.
- The initial seven-case source regression run failed all seven cases at the
  absent HTML header/value while its CSV and JSON parity assertions succeeded.

No fetch or other live repository query was performed.

## Exact cause and narrow fix

All three formats receive the same result row dictionaries:

- CSV uses `base_window.EXPORT_FIELDS`, built from audit output fields plus
  `schema.EXPORT_EXTRA_FIELDS`; `device_change` enters through
  `schema.INSIGHTS_EXTRA_COLUMNS`.
- Versioned JSON schema v2 deliberately copies each complete row, converts it to
  JSON-safe values and adds serialized provider evidence.
- HTML uses `device_insights.write_html_report`, whose table columns are manually
  assembled. That fixed table included status, package, Store fields, device
  comparison/compatibility, Maintenance Score and Notes, but had no
  `Device Inventory Change` header and no `device_change` cell.

The correction adds exactly one HTML column. Its heading uses the established
user-facing label **Device Inventory Change**. Each row reads the existing
`device_change` result field directly and HTML-escapes it. Missing/falsey values
produce the same empty-cell convention as neighboring HTML fields. No derived
inventory state, internal history flag or machine-only value is exposed.

## Regression coverage

`tests/test_html_device_change_export.py` adds seven deterministic cases:

1. `Same` (no inventory change);
2. `Installer changed`;
3. `Version changed`;
4. `New on device`;
5. a normal row without `device_change`, retaining a present blank column;
6. special-character/markup escaping in the new cell;
7. multi-row semantic parity across CSV, JSON and HTML for package population,
   Maintenance Score, Device Inventory Change and Store status, plus the existing
   JSON/HTML provider evidence boundary.

Formatting is intentionally format-specific. CSV remains a fixed flat schema,
JSON remains the versioned structured schema, and HTML remains the existing
user-facing report.

## Source gate

| Gate | Python 3.13.15 x64 / PySide6 6.11.1 | Python 3.14.6 x64 / PySide6 6.11.2 |
| --- | --- | --- |
| New focused regression file | 7 passed | 7 passed |
| Focused export/presentation suite | 90 passed | 90 passed |
| Full pytest | 718 passed, 14.81 s | 718 passed, 12.69 s |
| compileall / Quality helper compilation | PASS | PASS |
| Repository-wide Ruff | PASS | PASS |
| pip check | PASS | PASS |
| Canonical Qt source/offscreen smoke | PASS | PASS |

PowerShell helper syntax and `git diff --check` also pass. Validation ran with
outbound HTTP/HTTPS/ALL proxy variables pointed at the refusing loopback endpoint
and pip network access disabled. No dependency was installed or downloaded.

## Scope confirmation

Production behavior changes only in the HTML table mapping. There is no change to
ScanSession, ADB/device paths, RC6-D2A-001 lifecycle ordering, inventory comparison
or promotion semantics, Maintenance Score, F-Droid, Aptoide, credentials, CSV
fields, JSON schema/version, UI layout, dependencies, builder or release tooling.

No Nuitka command, RC7 rebuild, RC8 build, packaged smoke, provider-cleanup run,
remote operation or performance benchmark occurred. One local commit is authorized:
`fix: include device changes in html export`, with the exact parent above. That
commit is the **RC8 SOURCE CANDIDATE** only; packaging and acceptance require a
separate session.
