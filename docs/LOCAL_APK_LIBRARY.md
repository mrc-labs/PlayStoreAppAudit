# Persistent Local APK Library core

Last updated: 2026-09-10

## Scope and ownership

The v2.0 phase 5a core provides a Qt-independent persistent Local APK Library.
`playstore_app_audit.domain.local_apk_library` owns its immutable typed state and
operation results; `playstore_app_audit.services.local_apk_library` owns root
registration, explicit recursive scans, schema validation and atomic JSON
persistence. The end-user Library UI is phase 5b and is not yet implemented.

The Library is stored as `local_apk_library.json` in the active application-data
directory resolved by `playstore_app_audit.platform.runtime.app_data_dir()`, so
normal and portable modes retain their existing cross-platform behavior. It is
not stored in settings, audit history, Device Inventory, ScanSession, or either
Store/provider cache.

## Three separate identities

The Library deliberately keeps three concepts distinct:

- `artifact_sha256` identifies one exact sequence of APK bytes;
- `package_lookup_key`/`package_id` identifies the Android package used for a
  later Store lookup;
- `path` identifies one local physical location.

Artifacts are logically keyed by SHA-256. Path-independent parser metadata is
stored once per artifact. Location records point to an artifact SHA-256 and
carry only the registered root, usable absolute path, filename, modified time,
presence, and first/last-seen times. Two paths containing identical bytes are
therefore one artifact with two locations. If bytes at a path change, the old
path/SHA association is retained as not present and a new association points to
the new SHA; the old artifact identity is never mutated or automatically
deleted.

## Schema and writes

The JSON document starts at schema version `1` and explicitly separates
`roots`, `artifacts`, and `locations`. Loads validate types, enum values,
timestamps, SHA-256 values, unique identities, registered-root relationships,
and current path associations. Unknown schema versions, malformed JSON, and
invalid documents return typed failures. A failed load never creates or
overwrites a replacement document.

Serialization orders roots by normalized path, artifacts by SHA-256, and
locations by SHA-256/path. A save writes complete UTF-8 JSON to a sibling
temporary file, flushes and synchronizes it, then atomically replaces the
destination with `os.replace`. Save failures are typed and leave the previous
destination out of the partial-write path.

## Explicit recursive scans

Registered roots are normalized absolute local paths and exact duplicates are
collapsed. Scanning is explicit: there is no watcher or background monitor.
Traversal is deterministic, considers `.apk` case-insensitively, ignores
`.apks`, `.aab`, and other files, and does not follow directory symlinks or
reparse points. Every discovered candidate goes through the existing bounded
`parse_local_apk()` boundary; no ZIP, AXML, or resource parsing is duplicated.

Cancellation uses a caller-owned `threading.Event` and is checked between
directories and files. A progress callback receives typed root/current-path and
discovered/parsed counts suitable for later Qt worker integration. Issues are
typed and retained up to a configurable bound, with an omitted count after that
limit.

Valid artifacts survive unrelated parser, file, or directory failures. Parser
warnings remain artifact metadata. Parser rejection of a candidate does not
fail traversal of its root. An inaccessible directory makes that root scan
partial; an unavailable root makes it failed; cancellation makes it cancelled.
Only a fully completed root traversal may mark an unseen prior location as not
present. Partial, failed, and cancelled scans never infer wholesale deletion.
Historical artifacts and locations are retained; cleanup and duplicate
management are later v2.x concerns.

## Store and audit boundary

Scanning and persistence perform no Store, F-Droid, Aptoide, cache, or other
network operation and persist no remote evidence. Local paths and APK metadata
remain local application state.

`LocalApkLibraryService.auditable_artifacts()` reconstructs current
`LocalArtifact` inputs for the existing `LocalArtifactStoreService.collect()`
boundary. It selects one deterministic present location per exact SHA-256, so
identical physical copies do not create repeated Store-facing artifact inputs.
Different SHA-256 values remain distinct even when their package ID matches.
This does not change transient `Choose APK(s)`: explicitly selected files still
produce one transient row per selected valid file.

## Deferred to phase 5b and later

Phase 5b will add the Qt Library surfaces for adding folders, explicit rescans,
viewing current/missing locations, and launching audits through the existing
fan-out boundary. Watchers, deletion, duplicate cleanup, mass rename, Explorer
integration, APK installation, certificate/signature work, split APKs,
`.apks`, and `.aab` remain outside this core.
