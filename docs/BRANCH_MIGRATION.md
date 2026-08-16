# Branch migration plan

Do this only after the refactored Qt build is green in CI and has been tested with a real Android phone.

The important distinction is: **do not merge every legacy branch into `main`**. Only the current `qt6` application should be merged. `customtkinter` is preserved as a historical tag and then retired; `qt6-working` contains no unique work that needs merging.

## 1. Preserve checkpoints before changing branches

`qt6-working` has no unique commits relative to the current Qt branch, so a preservation tag is not necessary.

Keep a permanent checkpoint of the retired CustomTkinter implementation:

```bash
git fetch origin
git tag legacy-customtkinter-v9.3 origin/customtkinter
git push origin legacy-customtkinter-v9.3
```

Also preserve the pre-migration `main` state:

```bash
git tag pre-qt-main-migration origin/main
git push origin pre-qt-main-migration
```

## 2. Merge the Qt application into `main`

Do not force-reset `main`. Preserve history with a normal pull request/merge.

1. Open a pull request from `qt6` into `main`.
2. Review the small `main`-only documentation difference and resolve it in favour of the new architecture where appropriate.
3. Merge the pull request.
4. In the merged Windows workflow, change the automatic branch trigger from `qt6` to `main`.
5. Commit that workflow change on `main`.
6. Confirm a successful Windows build from `main`.
7. Test the resulting executable with a real Android phone.

`main` is already the repository default branch, so no default-branch switch is required.

## 3. Retire the legacy branches

Only after `main` is green and tested, delete:

- `customtkinter`
- `qt6-working`
- `qt6`

GitHub UI: repository → **Branches** → delete each branch using the trash/delete control.

CLI equivalent:

```bash
git push origin --delete customtkinter
git push origin --delete qt6-working
git push origin --delete qt6
```

The `legacy-customtkinter-v9.3` tag keeps the complete old CustomTkinter checkpoint without requiring a permanent branch.

## 4. Future workflow

From that point, `main` is the single canonical branch. Use short-lived feature/fix branches and merge them back into `main`.

Do not maintain permanent branches for Windows, macOS or Linux. All three desktop builds must come from the same source revision.
