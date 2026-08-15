from __future__ import annotations

from playstore_audit_customtkinter_v9 import CustomTkPlayStoreAuditV9


class CustomTkPlayStoreAuditV9Stable(CustomTkPlayStoreAuditV9):
    """Small stability wrapper for menu state that does not alter v9 features."""

    def _set_view_preset(self, name: str) -> None:
        super()._set_view_preset(name)
        # Rebuild the native Tk menu after a radio selection so exactly the
        # current view is marked on the next open.
        self._build_menu_v9()


def main() -> None:
    app = CustomTkPlayStoreAuditV9Stable()
    app.mainloop()


if __name__ == "__main__":
    main()
