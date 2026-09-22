# Store App Audit v2.1 — post-release closure handoff

Last updated: 2026-09-23 CEST

## Status

v2.1.0 is published, independently verified and immutable. Product and release work is complete. This handoff now exists only to carry the permanent closure documentation PR through normal merge, synchronize the normal local checkout, close/update issue #153 as appropriate, and generate the final post-merge snapshot/handoff.

Do not rebuild, retag, move, replace or upload anything to the v2.1.0 release.

## Immutable v2.1.0 release

- Release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v2.1.0
- Published: `2026-09-22T22:11:47Z`
- Release ID: `394150624`
- Frozen source SHA: `df2726b959963e5dbb096638d5072bd15eb1de92`
- Annotated tag object: `a0f7000e7e95cc5d0d075bfbf44c7b3debae7f58`
- Tag peel target: `df2726b959963e5dbb096638d5072bd15eb1de92`
- Quality #592 / run `35775208797`: PASS
- Windows final run `35776095408`: x64 + ARM64 PASS
- Linux final run `35776120755`: x64 + ARM64 PASS
- macOS final run `35776146620`: x64 + ARM64 PASS
- Windows/Linux: unsigned
- macOS: ad-hoc engineering signed; not Developer ID signed and not notarized

Exactly eight project-defined assets were published:

1. `PlayStoreAppAudit-v2.1.0-windows-x64.zip`
2. `PlayStoreAppAudit-v2.1.0-windows-arm64.zip`
3. `PlayStoreAppAudit-v2.1.0-linux-x64.zip`
4. `PlayStoreAppAudit-v2.1.0-linux-arm64.zip`
5. `PlayStoreAppAudit-v2.1.0-macos-x64.zip`
6. `PlayStoreAppAudit-v2.1.0-macos-arm64.zip`
7. `PlayStoreAppAudit-v2.1.0-third-party-sources.tar.xz`
8. `SHA256SUMS.txt`

Canonical assembly, release-layout validation and independent SHA-256 recomputation passed before publication. After publication, all eight assets were downloaded into a fresh directory; names, sizes, payload hashes and the checksum file matched, and every public file was byte-for-byte identical to the accepted local final set. No platform binary was rebuilt or repackaged.

## Post-release Actions housekeeping

Manual `actions-retention.yml` run `35793158003` completed successfully from the frozen `main` SHA with the existing retention algorithm and settings.

- Automated policy deletion: expired failed/cancelled runs `35023120949`, `35023486423`, `35023585122`, `35023610443`.
- Explicit post-release deletion: superseded candidate runs `35708299383`, `35708322474`, `35731253986` and their six invalidated/pre-final platform artifacts.
- Retained canonical v2.1 evidence: the six final artifacts from runs `35776095408`, `35776120755` and `35776146620`.
- Retained historical evidence: v1.99 assembler artifact `10123756577`.
- Remaining storage: 7 artifacts / 1,344,361,022 bytes (1,282.08 MiB / 1.252 GiB).
- The public release remained unchanged after housekeeping.

## Product scope outcome

v2.1 shipped:

- safe single-file Local APK Rename/Remove;
- validated collision-safe Mass Rename and guarded exact Outdated/Unknown Mass Remove;
- Device Specific resolution for phone and Local APK paths with raw public Store evidence preserved;
- Personal Google Session and Advanced Custom Dispenser metadata paths;
- privacy-safe process-local **Get Phone Data** Personal Device profile capture;
- theme-aware semantic presentation;
- canonical synthetic README and in-app Overview screenshots;
- source-transition and Installer Category presentation fixes.

Persistent Personal Device profile storage issue #200 was deliberately excluded and remains post-v2.1. Production-trust signing/notarization issue #154 also remains future work.

## Closure PR continuation point

The focused closure branch is `docs/v2.1-post-release-closure`, created from frozen release SHA/current `origin/main` `df2726b959963e5dbb096638d5072bd15eb1de92`.

The closure change is documentation-only. Its eventual merge commit will become a newer post-release `main` SHA and must remain clearly distinct from the immutable release SHA above.

Issue #153 is still open and must not be closed before this closure PR is merged and the final synchronization procedure is complete.

No v2.2 implementation has started. CLI/headless and Named Custom Views #147 remain candidates, not a frozen next-release contract. Issue #200 remains separate post-v2.1 work.

## Required next sequence

1. Review the complete closure documentation diff and require documentation validation/Quality to pass.
2. Merge the closure PR with a normal merge commit; do not squash or rebase.
3. Before synchronizing the normal checkout, run `git status --short` and stop if it is dirty.
4. On a clean checkout, run `git fetch --prune origin`, switch to `main`, and use `git pull --ff-only origin main`.
5. Verify local `HEAD` equals the canonical documentation-only post-release `main` SHA and the tree is clean.
6. Update/close issue #153 only after the merged documentation and synchronized workspace agree.
7. Only then generate `REPOSITORY_SNAPSHOT.md` and any final chat/continuation export.

Do not generate the final snapshot or handoff package from this pre-merge branch.

## One-line state summary

**v2.1.0 is published and immutable; complete the documentation-only closure PR, merge normally, synchronize clean local `main`, close/update #153, and only then generate the final snapshot/handoff before deliberate v2.2 scope selection.**
