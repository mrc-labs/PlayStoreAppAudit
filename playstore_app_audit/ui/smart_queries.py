from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.smart_queries as smart_queries


class ConditionRow(QWidget):
    changed = Signal()
    remove_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SmartQueryConditionRow")
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        root.addLayout(layout)

        self.field_combo = QComboBox()
        self.field_combo.setObjectName("SmartQueryField")
        self.field_combo.setAccessibleName("Condition Field")
        self.field_combo.setMinimumWidth(175)
        for definition in smart_queries.FIELD_DEFINITIONS:
            self.field_combo.addItem(definition.label, definition.field_id)
        layout.addWidget(self.field_combo, 3)

        self.operator_combo = QComboBox()
        self.operator_combo.setObjectName("SmartQueryOperator")
        self.operator_combo.setAccessibleName("Condition Operator")
        self.operator_combo.setMinimumWidth(180)
        layout.addWidget(self.operator_combo, 3)

        self.value_stack = QStackedWidget()
        self.value_stack.setObjectName("SmartQueryValueStack")
        self.value_stack.setMinimumWidth(175)

        self.text_value = QLineEdit()
        self.text_value.setObjectName("SmartQueryTextValue")
        self.text_value.setAccessibleName("Condition Value")
        self.text_value.setMaxLength(500)
        self.value_stack.addWidget(self.text_value)

        self.choice_value = QComboBox()
        self.choice_value.setObjectName("SmartQueryChoiceValue")
        self.choice_value.setAccessibleName("Condition Value")
        self.value_stack.addWidget(self.choice_value)

        self.number_value = QSpinBox()
        self.number_value.setObjectName("SmartQueryNumberValue")
        self.number_value.setAccessibleName("Condition Value")
        self.number_value.setRange(0, 1_000_000)
        self.value_stack.addWidget(self.number_value)

        self.date_value = QDateEdit()
        self.date_value.setObjectName("SmartQueryDateValue")
        self.date_value.setAccessibleName("Condition Value")
        self.date_value.setCalendarPopup(True)
        self.date_value.setDisplayFormat("yyyy-MM-dd")
        self.date_value.setDate(QDate.currentDate())
        self.value_stack.addWidget(self.date_value)

        self.no_value = QWidget()
        self.no_value.setObjectName("SmartQueryNoValue")
        self.value_stack.addWidget(self.no_value)
        layout.addWidget(self.value_stack, 3)

        self.remove_button = QToolButton()
        self.remove_button.setObjectName("RemoveSmartQueryCondition")
        self.remove_button.setAccessibleName("Remove Condition")
        self.remove_button.setToolTip("Remove condition")
        self.remove_button.setText("×")
        remove_font = self.remove_button.font()
        remove_font.setBold(True)
        remove_font.setPointSize(remove_font.pointSize() + 2)
        self.remove_button.setFont(remove_font)
        self.remove_button.setFixedSize(28, 28)
        layout.addWidget(self.remove_button)

        self.validation_label = QLabel()
        self.validation_label.setObjectName("SmartQueryConditionValidation")
        self.validation_label.setAccessibleName("Condition Validation")
        self.validation_label.setStyleSheet("color: #9B1C1C;")
        self.validation_label.hide()
        root.addWidget(self.validation_label)

        self.field_combo.currentIndexChanged.connect(self._on_field_changed)
        self.operator_combo.currentIndexChanged.connect(self._on_operator_changed)
        self.text_value.textChanged.connect(self.changed)
        self.choice_value.currentIndexChanged.connect(self.changed)
        self.number_value.valueChanged.connect(self.changed)
        self.date_value.dateChanged.connect(self.changed)
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        self._on_field_changed()

    def _definition(self) -> smart_queries.FieldDefinition:
        field_id = str(self.field_combo.currentData() or "")
        definition = smart_queries.field_definition(field_id)
        return definition or smart_queries.FIELD_DEFINITIONS[0]

    def _operator(self) -> smart_queries.Operator:
        value = str(self.operator_combo.currentData() or "")
        try:
            return smart_queries.Operator(value)
        except ValueError:
            return smart_queries.operators_for_field(self._definition().field_id)[0]

    def _on_field_changed(self) -> None:
        definition = self._definition()
        self.operator_combo.clear()
        for operator in smart_queries.operators_for_field(definition.field_id):
            self.operator_combo.addItem(smart_queries.OPERATOR_LABELS[operator], operator.value)
        self.choice_value.clear()
        for choice in definition.choices:
            self.choice_value.addItem(choice.label, choice.value)
        self.text_value.clear()
        self.number_value.setValue(0)
        self.date_value.setDate(QDate.currentDate())
        self._update_value_editor()
        if not self._loading:
            self.changed.emit()

    def _on_operator_changed(self) -> None:
        self._update_value_editor()
        if not self._loading:
            self.changed.emit()

    def _update_value_editor(self) -> None:
        definition = self._definition()
        operator = self._operator()
        if operator in {
            smart_queries.Operator.IS_EMPTY,
            smart_queries.Operator.IS_NOT_EMPTY,
            smart_queries.Operator.IS_YES,
            smart_queries.Operator.IS_NO,
        }:
            widget = self.no_value
        elif operator == smart_queries.Operator.WITHIN_LAST_DAYS:
            widget = self.number_value
        elif definition.field_type == smart_queries.FieldType.TEXT:
            widget = self.text_value
        elif definition.field_type == smart_queries.FieldType.CHOICE:
            widget = self.choice_value
        elif definition.field_type == smart_queries.FieldType.NUMBER:
            widget = self.number_value
        else:
            widget = self.date_value
        self.value_stack.setCurrentWidget(widget)

    def set_condition(self, condition: smart_queries.SmartCondition) -> None:
        self._loading = True
        try:
            field_index = self.field_combo.findData(condition.field)
            if field_index >= 0:
                self.field_combo.setCurrentIndex(field_index)
            operator_index = self.operator_combo.findData(condition.operator.value)
            if operator_index >= 0:
                self.operator_combo.setCurrentIndex(operator_index)
            definition = self._definition()
            if definition.field_type == smart_queries.FieldType.TEXT:
                self.text_value.setText(str(condition.value or ""))
            elif definition.field_type == smart_queries.FieldType.CHOICE:
                choice_index = self.choice_value.findData(condition.value)
                if choice_index >= 0:
                    self.choice_value.setCurrentIndex(choice_index)
            elif condition.operator == smart_queries.Operator.WITHIN_LAST_DAYS:
                self.number_value.setValue(int(condition.value or 0))
            elif definition.field_type == smart_queries.FieldType.NUMBER:
                self.number_value.setValue(int(float(condition.value or 0)))
            elif definition.field_type == smart_queries.FieldType.DATE:
                parsed = QDate.fromString(str(condition.value or ""), Qt.DateFormat.ISODate)
                if parsed.isValid():
                    self.date_value.setDate(parsed)
            self._update_value_editor()
        finally:
            self._loading = False
        self.changed.emit()

    def condition(self) -> smart_queries.SmartCondition | None:
        definition = self._definition()
        operator = self._operator()
        if self.value_stack.currentWidget() is self.text_value:
            value: object = self.text_value.text()
        elif self.value_stack.currentWidget() is self.choice_value:
            value = self.choice_value.currentData()
        elif self.value_stack.currentWidget() is self.number_value:
            value = self.number_value.value()
        elif self.value_stack.currentWidget() is self.date_value:
            value = self.date_value.date().toString(Qt.DateFormat.ISODate)
        else:
            value = None
        return smart_queries.normalise_condition(
            {"field": definition.field_id, "operator": operator.value, "value": value}
        )

    def set_validation_error(self, message: str) -> None:
        self.validation_label.setText(message)
        self.validation_label.setVisible(bool(message))


class SmartQueryDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        apply_callback: Callable[[smart_queries.SmartQuery], None],
        delete_callback: Callable[[str], None],
        new_query: bool = False,
        selected_query_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SmartQueryDialog")
        self.setWindowTitle("Smart Queries")
        self.setMinimumSize(780, 520)
        self.resize(920, 620)
        self._apply_callback = apply_callback
        self._delete_callback = delete_callback
        self._queries: list[smart_queries.SmartQuery] = []
        self._condition_rows: list[ConditionRow] = []
        self._draft_id = str(uuid4())
        self._selected_query_id: str | None = None
        self._can_apply = bool(getattr(parent, "current_rows", []))

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        content = QHBoxLayout()
        content.setSpacing(14)
        root.addLayout(content, 1)

        saved_host = QWidget()
        saved_layout = QVBoxLayout(saved_host)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_layout.setSpacing(6)
        saved_label = QLabel("Saved Queries")
        saved_layout.addWidget(saved_label)
        self.saved_list = QListWidget()
        self.saved_list.setObjectName("SmartQuerySavedList")
        self.saved_list.setAccessibleName("Saved Smart Queries")
        self.saved_list.setMinimumWidth(190)
        self.saved_list.setMaximumWidth(240)
        saved_label.setBuddy(self.saved_list)
        saved_layout.addWidget(self.saved_list, 1)
        self.new_button = QPushButton("New")
        self.new_button.setObjectName("NewSmartQueryDraft")
        self.new_button.setToolTip("Start a new Smart Query")
        saved_layout.addWidget(self.new_button)
        content.addWidget(saved_host)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)
        content.addWidget(editor, 1)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("SmartQueryName")
        self.name_edit.setAccessibleName("Smart Query Name")
        self.name_edit.setMaxLength(smart_queries.MAX_NAME_LENGTH)
        form.addRow("Name", self.name_edit)
        self.match_combo = QComboBox()
        self.match_combo.setObjectName("SmartQueryMatch")
        self.match_combo.setAccessibleName("Condition Match Mode")
        self.match_combo.addItem("All Conditions", smart_queries.MatchMode.ALL.value)
        self.match_combo.addItem("Any Condition", smart_queries.MatchMode.ANY.value)
        form.addRow("Match", self.match_combo)
        editor_layout.addLayout(form)

        header = QHBoxLayout()
        header.setSpacing(7)
        for text, stretch in (("Field", 3), ("Operator", 3), ("Value", 3)):
            label = QLabel(text)
            label.setObjectName("SmartQueryColumnLabel")
            header.addWidget(label, stretch)
        spacer = QWidget()
        spacer.setFixedWidth(28)
        header.addWidget(spacer)
        editor_layout.addLayout(header)

        self.condition_host = QWidget()
        self.condition_host.setObjectName("SmartQueryConditions")
        self.condition_layout = QVBoxLayout(self.condition_host)
        self.condition_layout.setContentsMargins(0, 0, 0, 0)
        self.condition_layout.setSpacing(7)
        self.condition_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setObjectName("SmartQueryConditionsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.condition_host)
        editor_layout.addWidget(scroll, 1)

        editor_commands = QHBoxLayout()
        self.add_condition_button = QPushButton("Add Condition")
        self.add_condition_button.setObjectName("AddSmartQueryCondition")
        editor_commands.addWidget(self.add_condition_button)
        editor_commands.addStretch(1)
        editor_layout.addLayout(editor_commands)

        self.validation_label = QLabel()
        self.validation_label.setObjectName("SmartQueryValidation")
        self.validation_label.setWordWrap(True)
        editor_layout.addWidget(self.validation_label)

        commands = QHBoxLayout()
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("DeleteSmartQuery")
        commands.addWidget(self.delete_button)
        commands.addStretch(1)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("SaveSmartQuery")
        commands.addWidget(self.save_button)
        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("ApplySmartQuery")
        commands.addWidget(self.apply_button)
        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("CloseSmartQueryDialog")
        commands.addWidget(self.close_button)
        root.addLayout(commands)

        self.saved_list.currentItemChanged.connect(self._on_saved_selection_changed)
        self.new_button.clicked.connect(self._new_draft)
        self.name_edit.textChanged.connect(self._sync_validation)
        self.match_combo.currentIndexChanged.connect(self._sync_validation)
        self.add_condition_button.clicked.connect(self._add_blank_condition)
        self.delete_button.clicked.connect(self._delete_selected)
        self.save_button.clicked.connect(self._save_draft)
        self.apply_button.clicked.connect(self._apply_draft)
        self.close_button.clicked.connect(self.reject)

        self._reload_saved_queries(select_id=selected_query_id)
        if new_query or not self._queries:
            self._new_draft()
        elif self.saved_list.count() and self.saved_list.currentRow() < 0:
            self.saved_list.setCurrentRow(0)

    def _reload_saved_queries(self, *, select_id: str | None = None) -> None:
        self._queries = smart_queries.load_queries()
        self.saved_list.blockSignals(True)
        self.saved_list.clear()
        selected_row = -1
        for index, query in enumerate(self._queries):
            item = QListWidgetItem(query.name)
            item.setData(Qt.ItemDataRole.UserRole, query.query_id)
            self.saved_list.addItem(item)
            if query.query_id == select_id:
                selected_row = index
        self.saved_list.blockSignals(False)
        if selected_row >= 0:
            self.saved_list.setCurrentRow(selected_row)

    def _clear_condition_rows(self) -> None:
        while self._condition_rows:
            row = self._condition_rows.pop()
            self.condition_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()

    def _add_condition(
        self, condition: smart_queries.SmartCondition | None = None
    ) -> ConditionRow:
        row = ConditionRow(self.condition_host)
        row.changed.connect(self._sync_validation)
        row.remove_requested.connect(self._remove_condition)
        self.condition_layout.insertWidget(max(0, self.condition_layout.count() - 1), row)
        self._condition_rows.append(row)
        if condition is not None:
            row.set_condition(condition)
        self._renumber_conditions()
        self._sync_validation()
        return row

    def _add_blank_condition(self) -> None:
        if len(self._condition_rows) < smart_queries.MAX_CONDITIONS:
            self._add_condition()

    def _remove_condition(self, target: object) -> None:
        if len(self._condition_rows) <= 1 or not isinstance(target, ConditionRow):
            return
        self._condition_rows.remove(target)
        self.condition_layout.removeWidget(target)
        target.setParent(None)
        target.deleteLater()
        self._renumber_conditions()
        self._sync_validation()

    def _renumber_conditions(self) -> None:
        only_one = len(self._condition_rows) <= 1
        for index, row in enumerate(self._condition_rows, start=1):
            row.setAccessibleName(f"Condition {index}")
            row.remove_button.setEnabled(not only_one)
        self.add_condition_button.setEnabled(
            len(self._condition_rows) < smart_queries.MAX_CONDITIONS
        )

    def _new_draft(self) -> None:
        self.saved_list.clearSelection()
        self.saved_list.setCurrentRow(-1)
        self._selected_query_id = None
        self._draft_id = str(uuid4())
        self.name_edit.clear()
        self.match_combo.setCurrentIndex(0)
        self._clear_condition_rows()
        self._add_condition()
        self.name_edit.setFocus()

    def _on_saved_selection_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        query_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        query = next((item for item in self._queries if item.query_id == query_id), None)
        if query is None:
            return
        self._selected_query_id = query.query_id
        self._draft_id = query.query_id
        self.name_edit.setText(query.name)
        match_index = self.match_combo.findData(query.match.value)
        self.match_combo.setCurrentIndex(max(0, match_index))
        self._clear_condition_rows()
        for condition in query.conditions:
            self._add_condition(condition)
        self._sync_validation()

    def _draft(self, *, require_name: bool) -> smart_queries.SmartQuery | None:
        conditions = [row.condition() for row in self._condition_rows]
        if any(condition is None for condition in conditions):
            return None
        return smart_queries.create_query(
            self.name_edit.text(),
            str(self.match_combo.currentData() or smart_queries.MatchMode.ALL.value),
            [condition for condition in conditions if condition is not None],
            query_id=self._draft_id,
            require_name=require_name,
        )

    def _sync_validation(self) -> None:
        conditions = [row.condition() for row in self._condition_rows]
        for index, (row, condition) in enumerate(
            zip(self._condition_rows, conditions, strict=True), start=1
        ):
            row.set_validation_error(
                "Enter a valid value for this condition." if condition is None else ""
            )
            row.validation_label.setAccessibleDescription(
                f"Condition {index} requires a valid value." if condition is None else ""
            )
        complete = bool(conditions) and all(condition is not None for condition in conditions)
        has_name = bool(self.name_edit.text().strip())
        self.save_button.setEnabled(complete and has_name)
        self.apply_button.setEnabled(complete and self._can_apply)
        self.delete_button.setEnabled(self._selected_query_id is not None)
        if not complete:
            message = "Complete every condition before saving or applying this Smart Query."
        elif not has_name:
            message = "Enter a name to save, or apply this draft without saving."
        elif not self._can_apply:
            message = "Load or audit results before applying this Smart Query."
        else:
            message = ""
        self.validation_label.setText(message)
        self.validation_label.setVisible(bool(message))

    def _save_draft(self) -> None:
        query = self._draft(require_name=True)
        if query is None:
            return
        conflict = smart_queries.name_conflict(query.name, exclude_id=query.query_id)
        replace_name = False
        if conflict is not None:
            answer = QMessageBox.question(
                self,
                "Replace Smart Query?",
                f"A Smart Query named '{conflict.name}' already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            replace_name = True
        saved = smart_queries.save_query(query, replace_name=replace_name)
        if conflict is not None:
            self._delete_callback(conflict.query_id)
        self._selected_query_id = saved.query_id
        self._draft_id = saved.query_id
        self._reload_saved_queries(select_id=saved.query_id)
        self._refresh_parent_menu()

    def _apply_draft(self) -> None:
        query = self._draft(require_name=False)
        if query is not None and self._can_apply:
            self._apply_callback(query)

    def _delete_selected(self) -> None:
        query = next(
            (item for item in self._queries if item.query_id == self._selected_query_id),
            None,
        )
        if query is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Smart Query?",
            f"Delete the Smart Query '{query.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if smart_queries.delete_query(query.query_id):
            self._delete_callback(query.query_id)
        self._reload_saved_queries()
        self._new_draft()
        self._refresh_parent_menu()

    def _refresh_parent_menu(self) -> None:
        parent = self.parentWidget()
        menu = getattr(parent, "smart_queries_menu", None)
        if isinstance(menu, QMenu):
            populate_smart_queries_menu(parent, menu)


def populate_smart_queries_menu(window: object, menu: QMenu) -> None:
    menu.clear()
    new_action = menu.addAction("New Smart Query…", window._show_new_smart_query)  # type: ignore[attr-defined]
    manage_action = menu.addAction(
        "Manage Smart Queries…", window._show_manage_smart_queries  # type: ignore[attr-defined]
    )
    clear_action = menu.addAction(
        "Clear Active Smart Query", window._clear_smart_query  # type: ignore[attr-defined]
    )
    menu.addSeparator()

    active = getattr(window, "_active_smart_query", None)
    saved_actions: list[QAction] = []
    queries = smart_queries.load_queries()
    if not queries:
        empty = menu.addAction("No Saved Smart Queries")
        empty.setEnabled(False)
    else:
        for query in queries:
            action = QAction(query.name, menu, checkable=True)
            action.setChecked(isinstance(active, smart_queries.SmartQuery) and active == query)
            action.setToolTip(f"Apply Smart Query: {query.name}")
            action.triggered.connect(
                lambda _checked=False, selected=query: window._apply_smart_query(selected)  # type: ignore[attr-defined]
            )
            menu.addAction(action)
            saved_actions.append(action)

    window.new_smart_query_action = new_action  # type: ignore[attr-defined]
    window.manage_smart_queries_action = manage_action  # type: ignore[attr-defined]
    window.clear_smart_query_action = clear_action  # type: ignore[attr-defined]
    window.saved_smart_query_actions = saved_actions  # type: ignore[attr-defined]
    sync_smart_query_action_availability(window)


def sync_smart_query_action_availability(window: object) -> None:
    operation_running = getattr(window, "_operation_running", None)
    idle = not bool(operation_running()) if callable(operation_running) else True
    results_available = bool(getattr(window, "current_rows", []))
    active = isinstance(getattr(window, "_active_smart_query", None), smart_queries.SmartQuery)

    for name in ("new_smart_query_action", "manage_smart_queries_action"):
        action = getattr(window, name, None)
        if isinstance(action, QAction):
            action.setEnabled(idle)
    clear_action = getattr(window, "clear_smart_query_action", None)
    if isinstance(clear_action, QAction):
        clear_action.setEnabled(idle and active)
    for action in getattr(window, "saved_smart_query_actions", []) or []:
        if isinstance(action, QAction):
            action.setEnabled(idle and results_available)
    menu = getattr(window, "smart_queries_menu", None)
    if isinstance(menu, QMenu):
        menu.menuAction().setEnabled(idle)


def show_smart_query_dialog(
    window: QWidget,
    *,
    new_query: bool,
    selected_query_id: str | None = None,
) -> None:
    dialog = SmartQueryDialog(
        window,
        apply_callback=window._apply_smart_query,  # type: ignore[attr-defined]
        delete_callback=window._on_smart_query_deleted,  # type: ignore[attr-defined]
        new_query=new_query,
        selected_query_id=selected_query_id,
    )
    dialog.exec()
