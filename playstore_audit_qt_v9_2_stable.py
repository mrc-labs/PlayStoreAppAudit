from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app_icon import ensure_runtime_icon
import playstore_audit_qt_v9_2 as v92ui
import playstore_audit_v9_2_features as v92


class PlayStoreAuditQtV92Stable(v92ui.PlayStoreAuditQtV92):
    def _update_summary(self) -> None:
        if not hasattr(self, "summary_label"):
            return
        base_rows = self._rows_before_criticality_filter()
        criticality = v92ui.v9.v8.v7.qt_base.CRITICALITY
        counts = {
            key: sum(1 for row in base_rows if str(row.get("criticality_key") or "") == key)
            for key in criticality
        }
        if hasattr(self, "criticality_buttons"):
            for key, button in self.criticality_buttons.items():
                button.setText(f"{criticality[key]['button']} {counts[key]}")
        visible = self.proxy.rowCount() if hasattr(self, "proxy") else len(self.current_rows)
        self.summary_label.setText(v92.concise_summary(list(self.current_rows), visible))

    def _clear_results(self) -> None:
        self._status_filters.clear()
        super()._clear_results()
        if isinstance(self.proxy, v92ui.V92FilterProxy):
            self.proxy.set_status_filters(set())
        self._sync_status_filter_buttons()
        self._update_summary()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(v92ui.v9.v8.v7.qt_base.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = PlayStoreAuditQtV92Stable()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
