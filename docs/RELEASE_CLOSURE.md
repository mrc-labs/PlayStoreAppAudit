# Release Closure and Workspace Synchronization

## Purpose

This document defines the permanent release-closure procedure for Store App Audit. It applies to every release line and every future release unless a later explicit engineering decision replaces it.

A release is not operationally complete when the GitHub Release is merely published. Release closure is complete only when the remote repository, the local VS Code checkout, and the maintained project-context documentation all describe the same canonical state.

## Permanent release-closure invariant

Every release must end with all of the following completed:

1. The intended release/tag/assets are published and independently verified according to the active release profile.
2. Post-release repository housekeeping is complete.
3. The canonical `main` branch contains the final documentation/context updates for the completed release and the next active development cycle.
4. The local VS Code workspace is synchronized to the canonical remote `main` without discarding local work.
5. The local checkout is verified clean and at the expected canonical SHA after synchronization.
6. The maintained Markdown/context files are reviewed and updated so future VS Code/Codex work and future chat handoffs start from current facts rather than stale release assumptions.
7. A fresh handoff/context export is generated from that clean, synchronized local checkout when a handoff package is needed.
8. The live GitHub repository/About metadata and rendered homepage README agree with the published product identity, latest release, supported platforms and signing state.
9. Local Docker availability/resources and local repository hygiene are reviewed without deleting ambiguous or shared resources.

Do not mark a release cycle closed while any of these steps is still pending.

## Canonical context files to review at every release close

Review every maintained project-context Markdown file and update every file whose facts, release state, workflow, roadmap, version, compatibility statement, or handoff instructions changed.

At minimum, explicitly review:

- `AGENTS.md`
- `README.md`
- `CHANGELOG.md`
- `docs/PROJECT_DECISIONS.md`
- `docs/PROJECT_STATUS.md`
- `docs/ROADMAP.md`
- `docs/BUILDING.md`
- `docs/RELEASE_NOTES.md`
- `docs/CI_MAINTENANCE.md`
- the current version-specific `docs/HANDOFF_V*.md`
- this `docs/RELEASE_CLOSURE.md`

Also review any newly added Markdown/context file that has become part of the project's operating knowledge. Historical release wording must remain historically accurate and must not be rewritten merely to match a newer roadmap.

`REPOSITORY_SNAPSHOT.md` is generated context, not a tracked source of truth. Generate it only from a clean, synchronized checkout and never treat an older snapshot as current repository state.

## Required post-release documentation state

Before closing a release, the maintained context must make the following unambiguous:

- latest published version and immutable release SHA;
- release class/profile, supported platform/architecture set and signing state;
- final release workflow/build/assembly evidence when applicable;
- canonical Actions run IDs, retained audit artifacts and the post-release storage check;
- public asset names and verification/checksum evidence when applicable;
- current canonical application version;
- current `main` development baseline;
- features shipped in the completed release;
- features intentionally removed or rejected;
- scope and priorities for the next release;
- any changed engineering, UX, packaging, dependency or release decisions;
- any validation still intentionally outstanding after publication, if such a state is explicitly allowed;
- the correct handoff file and continuation instructions for subsequent VS Code/Codex/chat work.

Do not leave a previous release described as the active development cycle after the next cycle begins.

Restore deliberately temporary release-window Python pins to rolling stable development tracking through the focused closure change when the final freshness record requires it. Keep the exact patch in immutable release evidence. Immediately before every future frozen release SHA, repeat final freshness and pin/assert one audited exact full patch across release-producing workflows and final Quality again.

## Live GitHub repository-page reconciliation

README/file updates alone do not complete repository-page reconciliation. At every release closure:

1. Inspect authenticated live repository metadata and the visible GitHub homepage: About description, homepage URL, topics, rendered README, latest published Release and Sponsors link.
2. Align the About description and README product identity with **Store App Audit**, latest published version, actual platforms/support and actual signing/notarization state; remove current-looking release-preparation claims after publication.
3. Preserve the technical `PlayStoreAppAudit` repository/executable/package slug and historical URLs. Review topics for relevance without cosmetic churn. Leave homepage empty unless a real canonical project website exists.
4. Record description, homepage and topics before/after. Use authenticated CLI/API for authorized metadata changes, then verify the live values; if unavailable, report the exact remaining manual change.
5. After the closure PR merges, inspect the rendered default-branch README again. A branch README preview does not establish that public `main` has already changed.

## Local Docker and repository hygiene

First determine whether Docker is installed and its daemon is running. When available, inspect `docker ps -a`, `docker images` and `docker system df`, plus volume/build-cache inventories where relevant. Record Ubuntu tags (especially 20.04/22.04/24.04), stopped containers, dangling images, packaging resources and possible dependencies from other local projects. If the daemon is unavailable, record that limitation and repeat the read-only inventory when it is running; do not infer an empty inventory.

Docker is not required for normal local Store App Audit source development or source Quality/smoke checks. Repository CI deliberately uses `ubuntu:22.04` containers for the x64 compatibility sysroot/probe and Ubuntu 22.04 packaged GUI/CLI backward smoke. The retired release-path component is the GitHub-hosted Ubuntu 22.04 **build runner**, not these compatibility containers. Ubuntu 24.04 build hosts do not justify removing them.

Prefer reporting individual cleanup candidates for maintainer/control-tower review. Do not run broad system/image/volume pruning or blind deletion. Delete a resource only with conclusive evidence that it is disposable and unshared; leave ambiguous resources intact.

Also inspect local branches and which are merged into `main`, worktrees, ignored `release-v*-candidate-*` directories and version-specific freshness/preparation/release working directories. Report candidates without automatic branch deletion, reset, stash, clean or discard. Keep release working material until durable evidence is recorded and closure review permits cleanup; preserve environments or archives still needed by other work.

## Actions storage closure

Complete the post-release Actions procedure in `CI_MAINTENANCE.md` before calling housekeeping finished:

1. verify the published tag, exact source SHA, asset names and checksums;
2. identify the canonical Quality, final build, assembler and publication runs;
3. verify which Actions artifacts came from the canonical release lineage;
4. confirm that no later workflow still consumes the candidate artifacts;
5. delete only redundant Actions copies and keep the intended final build/assembler audit artifacts;
6. re-check the published GitHub Release unchanged;
7. record the remaining Actions artifact count/storage and any retention lesson in current context documentation.

Failed/cancelled-run expiry and ordinary generation cleanup continue to follow `CI_MAINTENANCE.md`. Do not change retention settings without evidence that the existing policy is failing.

## Local VS Code synchronization procedure

The normal local repository is the user's VS Code development checkout. The exact filesystem path is machine-specific and must not be hard-coded as a repository invariant.

Before any local pull or synchronization:

```powershell
git status --short
```

If the working tree is dirty, stop. Do not automatically reset, stash, discard, overwrite, or clean the user's local work.

When clean, synchronize conservatively:

```powershell
git fetch --prune origin
git switch main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git log -1 --oneline
```

Then verify that:

- `git status --short` is empty;
- local `main` is the intended remote `main` state;
- `HEAD` equals the expected canonical post-release/documentation SHA;
- the expected release tag is visible locally after fetch;
- obsolete already-merged local branches are reviewed and may be deleted deliberately;
- no untracked or generated file is mistaken for canonical source/context.

Never use a forced reset or automatic stash as routine release housekeeping.

## Handoff/context export

Run `scripts/export_chat_handoff.ps1` only after the local checkout is clean and synchronized.

The export must contain the current version-specific handoff plus the canonical project context used to continue work. The generated `REPOSITORY_SNAPSHOT.md` must record the live local branch, HEAD, cleanliness, recent commits/tags, and available GitHub metadata.

A handoff created before the final documentation merge or before local synchronization is stale and must not be used as the canonical handoff for the next development cycle.

## Relationship to release publication

Publication immutability remains unchanged. Documentation and local-workspace closure happen after release verification without rebuilding, retagging, or replacing immutable published artifacts.

If a documentation-only post-release housekeeping commit is required after publication, it changes `main` context but does not change the already published release SHA or assets. The context must clearly distinguish the immutable release source SHA from the newer post-release `main` SHA.

## Future release requirement

Every new release-specific handoff and release checklist must inherit this procedure. Do not copy a shortened version that omits local VS Code synchronization or context-document review.

When starting a new release cycle, update the current handoff/export configuration as part of the cycle setup so the next closure produces a current, self-contained continuation package.
