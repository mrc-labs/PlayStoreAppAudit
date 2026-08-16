# Branch migration plan

Do this only after the refactored Qt build is green in CI and has been tested with a real Android phone.

## 1. Preserve optional legacy checkpoints

`qt6-working` has no unique commits relative to the current Qt branch, so a preservation tag is not necessary.

For the retired CustomTkinter implementation, optionally keep a permanent tag before deleting the branch:

```bash
git fetch origin
git tag legacy-customtkinter-v9.3 origin/customtkinter
git push origin legacy-customtkinter-v9.3
```

Also preserve the pre-migration main branch before changing it:

```bash
git tag pre-qt-main-migration origin/main
git push origin pre-qt-main-migration
```

## 2. Retire obsolete branches

After the tags exist and the Qt build is validated, delete:

- `qt6-working`
- `customtkinter`

GitHub UI: repository → **Branches** → delete the branch using the trash/delete control.

CLI equivalent:

```bash
git push origin --delete qt6-working
git push origin --delete customtkinter
```

## 3. Merge the Qt application into `main`

Do not force-reset `main`. Preserve history with a normal pull request/merge.

1. Open a PR from `qt6` into `main`.
2. Review the small `main`-only documentation difference and resolve it in favour of the new architecture where appropriate.
3. Merge the PR.
4. Change the automatic Windows workflow trigger from `qt6` to `main`.
5. Run/confirm a successful Windows build from `main`.
6. Test the resulting executable.

`main` is already the repository default branch, so no default-branch switch is required.

## 4. Retire the permanent `qt6` branch

Once `main` contains the refactored Qt application and its Windows build is green:

```bash
git push origin --delete qt6
```

From that point, use short-lived feature/fix branches and merge them back to `main`. Do not maintain permanent branches for Windows, macOS or Linux.
