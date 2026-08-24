# Smart Queries UX Review

Last updated: 2026-08-24

Status: **approved on 2026-08-24 and implemented in the dedicated v1.8 Smart Queries PR**.

The seven decisions recorded below are the approved implementation contract. Play Store icon hardening remains independent.

## Purpose

Smart Queries are named, reusable filters over audit results that are already loaded in the table. They help answer repeatable maintenance questions such as:

- apps that are stale and installed from an alternative source;
- apps with an old target SDK and a non-current maintenance status;
- disabled apps with a Store version difference;
- results with missing Store metadata.

"Smart" means a structured multi-condition query. It does not mean natural-language parsing, AI classification, background monitoring or an additional Play Store/ADB operation.

## Scope Boundaries

A Smart Query:

- changes only which existing result rows are visible;
- never changes Store country/language, cache policy, ADB collection or audit behavior;
- never starts or re-runs an audit;
- composes with search, status chips, system-app visibility, Quick Filters and the SDK Maintenance Filter;
- remains read-only with respect to the connected Android device;
- does not add a permanent vertical UI section.

Nested expression trees, scripting, regular expressions, query sharing/import, background execution and notifications are outside the proposed v1.8 scope.

## Distinction From Audit Profiles

| Area | Smart Query | Audit Profile |
| --- | --- | --- |
| Acts on | Results already loaded | Settings used by the next audit |
| Changes network/ADB work | No | Potentially, through audit settings |
| Typical content | Fields, operators and values | Country, language, cache, workers, device enrichment |
| Application timing | Immediate table filter | Before the next audit |
| UI location | View | Tools |
| Persistence namespace | `smart_queries` | `audit_profiles` |

The two concepts must not share save/apply commands or imply that an Audit Profile contains result filters.

## Recommended Model

Each saved query uses stable field/operator identifiers rather than display labels:

```json
{
  "schema_version": 1,
  "id": "4cf53e27-2d3a-4ab6-b24f-e9ba06f70bd8",
  "name": "Stale alternative-source apps",
  "match": "all",
  "conditions": [
    {"field": "age_days", "operator": "greater_or_equal", "value": 730},
    {"field": "installer_category", "operator": "is", "value": "alternative_store"}
  ]
}
```

Recommended constraints:

- `schema_version` starts at `1` and unknown versions are ignored safely;
- `id` is a generated UUID and remains stable when a query is renamed;
- `name` is trimmed, limited to 80 characters and unique case-insensitively;
- `match` is `all` or `any`;
- a query contains 1-20 ordered conditions;
- conditions are one level only, with no nested groups in v1.8;
- values are normalized by field type before storage and evaluation.

One-level All/Any logic covers the common workflows while keeping the builder and evaluator understandable. Nested Boolean groups should be reconsidered only after real usage demonstrates a need.

## Proposed Fields

The initial list should be curated rather than exposing every internal row key.

| Type | User-facing fields | Stable field IDs |
| --- | --- | --- |
| Text | Package Name, Play Store Title, Notes | `package_name`, `play_title`, `notes` |
| Choice | Status, Play Status, Installed vs Store, Installer Category, Android Compatibility, Enabled State, Device Inventory Change | `criticality_key`, `play_status`, `version_comparison`, `installer_category`, `compatibility_status`, `app_enabled`, `device_change` |
| Number | Age (Days), Target SDK, Min SDK, Sensitive Permissions Count, Health Score | `age_days`, `target_sdk`, `min_sdk`, `sensitive_permissions_count`, `health_score` |
| Date | Last Update, First Installed, Last Local Update | `play_last_update`, `first_install_time`, `last_local_update` |
| Boolean | System App | `is_system` |

Device-only fields remain available in saved definitions. When the current file/source audit has no value for one of those fields, normal missing-value semantics apply; the query is not silently rewritten or disabled.

Technical fields such as raw HTTP status, Store URL and internal evidence tokens are excluded from the initial builder. They can be evaluated later if a repeatable maintenance use case appears.

## Proposed Operators

| Field type | Operators |
| --- | --- |
| Text | Contains, Does Not Contain, Is, Is Not, Starts With, Is Empty, Is Not Empty |
| Choice | Is, Is Not, Is Empty, Is Not Empty |
| Number | Equals, Does Not Equal, Greater Than, Greater Than or Equal, Less Than, Less Than or Equal, Is Empty, Is Not Empty |
| Date | Is On, Is Before, Is After, Within the Last N Days, Is Empty, Is Not Empty |
| Boolean | Is Yes, Is No |

Evaluation rules:

- text comparison is case-insensitive and trims surrounding whitespace;
- numeric conversion failure is treated as a missing value;
- date comparison uses parsed calendar dates, not display-formatted strings;
- a missing field matches `Is Empty` and fails other positive comparisons;
- `Does Not Contain`, `Is Not` and `Does Not Equal` do not match missing values; use `Is Empty` explicitly when missing data is intended;
- conditions inside the Smart Query use its All/Any mode;
- the completed Smart Query is ANDed with every other active filtering surface.

The last rule preserves the current independent behavior of search, status chips, system-app visibility, Quick Filters and SDK maintenance filtering.

## Recommended UX

Rename the current **View > Filter Preset** menu to **View > Quick Filters** because it contains built-in one-click filters rather than user-defined presets. Add a sibling **View > Smart Queries** menu.

Proposed View menu segment:

```text
Quick Filters >
Smart Queries >
SDK Maintenance Filter...
Clear SDK Filter
```

The Smart Queries menu should contain:

```text
New Smart Query...
Manage Smart Queries...
Clear Active Smart Query
------------------------
<saved query names>
```

`Clear Active Smart Query` is disabled when none is active. Saved query actions are disabled when there are no results to filter, while New/Manage remain available whenever the application is idle.

### Builder and Manager

Use one native modal dialog rather than separate CRUD windows:

```text
+------------------+---------------------------------------------+
| Saved queries    | Name                                        |
|                  | Match [All | Any] of the following           |
| Query A          |                                             |
| Query B          | [Field] [Operator] [Value]        [Remove]   |
|                  | [Field] [Operator] [Value]        [Remove]   |
|                  |                                             |
|                  | [Add Condition]                              |
+------------------+---------------------------------------------+
| [Delete]                         [Save] [Apply] [Close]         |
+----------------------------------------------------------------+
```

Behavior:

- **New Smart Query** opens a blank one-condition draft;
- selecting a saved query loads it into the editor;
- changing the field resets incompatible operator/value controls;
- **Apply** evaluates the draft immediately without requiring a save;
- **Save** persists the definition but does not unexpectedly change the current table;
- replacing an existing case-insensitive name requires confirmation;
- **Delete** requires confirmation and clears the active query if it was deleted;
- invalid or incomplete conditions keep Save and Apply disabled with inline field-level feedback;
- technical status/progress text is not overwritten by presentation-only query changes.

An active query should be shown by check mark in the Smart Queries menu and by a compact suffix in the existing summary, for example `42/318 shown | Smart Query: Stale alternative-source apps`. This avoids another toolbar control or chip row while keeping hidden filtering discoverable.

The active query remains applied while results refresh or the source changes during the current application session, until explicitly cleared. It is not restored automatically after application restart; saved definitions remain available for deliberate reapplication.

## Persistence Recommendation

Use a versioned `smart_queries` value in existing settings storage plus a focused pure service module for validation/evaluation. This matches current repository patterns and avoids a new persistence subsystem.

Recommended stored shape:

```json
{
  "smart_queries": {
    "schema_version": 1,
    "items": [
      {"schema_version": 1, "id": "...", "name": "...", "match": "all", "conditions": []}
    ]
  }
}
```

Loading must normalize known fields/operators, discard malformed entries and preserve the normal atomic settings write path. Query definitions are local preferences and are not included in audit result exports or diagnostic bundles.

The hidden legacy `saved_filters` structure stores only search text, one criticality, hide-system and a built-in preset. It is not semantically equivalent to the proposed condition model. Recommendation: do not migrate or expose it automatically in v1.8. Leave the old key untouched for compatibility and consider a separately reviewed one-time import only if real user data justifies it.

## Performance and Correctness

- Normalize a query once when applied; do not parse operators for every row.
- Evaluate only in the existing proxy-filter path and trigger one filter invalidation per query change.
- Keep evaluation pure and side-effect free.
- Use stable internal values for Store status, maintenance status and installer category while presenting localized/human-readable labels in controls.
- Preserve uncertainty: an unavailable field or inconclusive Store status must not be converted into a definitive negative classification.
- Target smooth filtering for at least 10,000 in-memory rows and 20 conditions without network, disk or ADB work.

## Accessibility and Testing

The dialog needs tab order, accessible names for condition rows, keyboard-accessible Add/Remove controls and labels associated with every editor. Icon-only Remove controls require a tooltip.

Required implementation test groups:

- pure normalization and evaluation for every field type/operator;
- malformed/unknown schema handling;
- All/Any and missing-value semantics;
- persistence, rename, replacement and deletion;
- separation from Audit Profiles and legacy `saved_filters`;
- composition with search, chips, Quick Filters, system visibility and SDK filters;
- action availability with no results and during running operations;
- active-query summary/menu synchronization;
- 10,000-row performance regression;
- Qt accessibility and dialog layout at the supported Windows resolutions.

## Approved Decisions

The recommended v1.8 implementation baseline is:

1. User-facing names: **Quick Filters** for current built-ins and **Smart Queries** for saved structured filters.
2. One-level All/Any conditions only; no nested groups.
3. The curated field/operator list in this document.
4. One combined native builder/manager dialog plus a View-menu submenu; no permanent toolbar control.
5. Versioned `smart_queries` persistence in settings and session-only active state.
6. No automatic migration of hidden legacy `saved_filters`.
7. Smart Queries compose with all current filters and never affect audit execution.

These decisions were explicitly approved and implemented on 2026-08-24. The implementation must continue to enforce the scope boundaries in this document: Smart Queries remain result-only filters, stay separate from Audit Profiles and do not expand into nested groups, scripting, regular expressions, import/export or automation.
