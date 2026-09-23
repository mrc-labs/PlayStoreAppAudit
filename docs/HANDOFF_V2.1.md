# Store App Audit v2.1 — final editorial closure handoff

Last updated: 2026-09-23 CEST

## Current state

v2.1.0 is published, independently verified, and complete. Its immutable release source is `df2726b959963e5dbb096638d5072bd15eb1de92`.

The first post-release closure PR merged normally. Canonical `main` before the final editorial pass is `6c7d705f04cae4e4d497c14cc4b81d2d2a50b679`; post-merge Quality #594 / run `35796651559` passed.

The final editorial/roadmap work is on `docs/final-v2.1-editorial-roadmap`. No application source, version, dependency, workflow, release tag, or release asset is changed.

Issue #153 remains open. Do not generate `REPOSITORY_SNAPSHOT.md` or the final chat/handoff export until this final editorial PR is merged and the normal checkout is synchronized to the resulting `main` SHA.

## Immutable v2.1.0 release

- Release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v2.1.0
- Frozen source SHA: `df2726b959963e5dbb096638d5072bd15eb1de92`
- Annotated tag object: `a0f7000e7e95cc5d0d075bfbf44c7b3debae7f58`
- Quality #592 / run `35775208797`: PASS
- Windows `35776095408`, Linux `35776120755`, macOS `35776146620`: x64 + ARM64 PASS
- Windows/Linux: unsigned
- macOS: ad-hoc engineering signed; not Developer ID signed or notarized
- Exactly eight project-defined assets; checksum, clean public re-download, and byte-for-byte verification: PASS

The release source commit, annotated tag target, and all binary/source/checksum assets are immutable. Descriptive GitHub Release prose is editorially maintainable under `RELEASE_NOTES.md` when historical facts and semantics do not change.

## Final editorial pass

- All 13 published GitHub Release bodies, v2.1.0 through v1.0.0, were condensed into a consistent four-section structure.
- User-facing highlights now take precedence over internal engineering detail.
- Historical platform/signing limitations, frozen SHAs, checksums, and essential verification evidence remain.
- The corrupted dash encoding in the old v1.99.0 note was removed.
- Release titles, tags, asset IDs, names, sizes, and digests were not changed.
- `docs/RELEASE_NOTES.md` is the canonical repository mirror of the maintained public prose.

## Roadmap decisions

- Issue #208 is explicit v2.2 scope for source-aware automatic columns, separate persistent Custom layouts for phone/App List and Local APK source families, and source-aware built-in presets.
- Issue #147 remains the broader named Custom Views enhancement and is not redefined or closed by #208.
- CLI/headless remains planned for v2.2 through existing service/domain boundaries.
- Issue #200 remains separate post-v2.1 work for persistent Personal Device profiles.
- Issue #209 tracks later-2.x update notification/download and eventual self-update design; automatic installation is not v2.2 scope.
- Issue #209 is linked to signing/notarization trust issue #154.

## Local artifact cleanup

`artifact\` contained no tracked files and is ignored by `.gitignore`.

- Before: 6,008,445,053 bytes across 18,104 files.
- Deleted: 5,973,360,239 bytes of public re-downloads, assembled releases, virtual environments, Nuitka/build trees, old source/test copies, and preserved builder outputs.
- Retained: 35,084,814 bytes of small diagnostics, benchmark data, screenshots, scripts, and acceptance reports that may be unique.
- No ACL broadening was used and all 17 exact deletion targets succeeded.

## Required next sequence

1. Review and merge the final editorial PR with a normal merge commit; do not squash or rebase.
2. Confirm post-merge Quality passes.
3. On the normal checkout, require a clean `git status --short`, then fetch, switch to `main`, and pull with `--ff-only`.
4. Verify the clean local HEAD equals the canonical post-editorial `main` SHA.
5. Keep issue #153 open until the final synchronized closure state is confirmed.
6. Only then update/close #153 as directed and generate `REPOSITORY_SNAPSHOT.md` plus the final continuation export.

## One-line state summary

**v2.1.0 remains immutable; merge and synchronize the final prose/roadmap PR, then finish issue #153 and generate the final snapshot/handoff from clean canonical `main`.**
