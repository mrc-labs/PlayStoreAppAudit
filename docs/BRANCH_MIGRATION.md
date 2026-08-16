# Branch migration status

The Qt6 v0.10.0 application has been validated on a real Android phone and promoted to `main`.

`main` is now the canonical production branch. The old `main` commit remains preserved in the merge history. `qt6-working` has no commits that are unique relative to the promoted Qt history.

Because the GitHub connector cannot create Git tags directly, the final CustomTkinter head was preserved automatically as the temporary archival branch:

`archive/customtkinter-v9.3`

This points at the same commit that `customtkinter` pointed at when retirement started.

## Manual archival step

Convert that archival pointer into a permanent tag from any local clone:

```bash
git fetch origin
git tag legacy-customtkinter-v9.3 origin/archive/customtkinter-v9.3
git push origin legacy-customtkinter-v9.3
```

Verify the tag appears under GitHub **Tags** before deleting the archival branch.

A separate `pre-qt-main-migration` tag is optional rather than required: the former `main` commit remains a parent in the merge history, so it has not been discarded.

## Manual branch retirement

After the automatic Windows build from `main` is green, delete these migration branches:

- `customtkinter`
- `qt6-working`
- `qt6`
- `archive/customtkinter-v9.3` (only after the tag above exists)

GitHub UI: repository → **Branches** → use the delete/trash control for each branch.

CLI equivalent:

```bash
git push origin --delete customtkinter
git push origin --delete qt6-working
git push origin --delete qt6
git push origin --delete archive/customtkinter-v9.3
```

Do not merge `customtkinter` or `qt6-working` into `main`.

## Future workflow

`main` is the single permanent production branch. Use short-lived feature/fix branches, open a pull request back to `main`, merge it, then delete the temporary branch.

Do not maintain permanent Windows/macOS/Linux branches. All three desktop builds must come from the same source revision. Windows builds automatically; macOS and Linux remain manually dispatched only.
