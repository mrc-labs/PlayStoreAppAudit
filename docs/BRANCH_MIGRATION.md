# Branch migration status

The branch migration is complete.

- `main` is the single canonical permanent branch.
- The former `qt6`, `qt6-working`, `customtkinter` and temporary archival branch have been deleted.
- The final CustomTkinter implementation is preserved by the Git tag `legacy-customtkinter-v9.3`.
- The pre-Qt `main` state remains reachable through normal merge history, so no destructive history rewrite was used.

The historical CustomTkinter tag is not a maintained branch. It exists only as a named checkpoint that can be inspected, checked out or archived if the old implementation is ever needed for reference.

## Current workflow

Use short-lived branches such as:

```text
feature/...
fix/...
refactor/...
```

Open a pull request back to `main`, validate it, merge it, then delete the temporary branch.

Do not maintain permanent Windows/macOS/Linux branches. All three desktop builds must come from the same source revision. Windows builds automatically from `main`; macOS and Linux packaging remains manually dispatched only.

## Historical tag retention

`legacy-customtkinter-v9.3` does not disappear automatically and does not duplicate the repository contents. Git stores it as a lightweight pointer to the existing historical commit.

Keep it at least through Qt/cross-platform stabilisation and the first stable 1.x release. It can be deleted later if the old CustomTkinter implementation no longer has any reference value.
