# -*- coding: utf-8 -*-
"""
Master Data tab for managing Types de Décharges (Données de Base -> Types de Décharges).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.decharge_manager import DechargeManager
from ui.icons import apply_button_icon
from ui.theme_tokens import CLEAN_TABLE_QSS, DANGER_OUTLINE_QSS, PRIMARY_CTA_QSS, SLATE_OUTLINE_QSS


class _DechargeTypeDialog(QDialog):
    def __init__(self, type_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modifier Type de Décharge" if type_data else "Nouveau Type de Décharge")
        self.setModal(True)
        self.resize(420, 200)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        self.txt_name = QLineEdit(str((type_data or {}).get("Type_Name") or ""))
        self.txt_name.setPlaceholderText("Ex : Loyer, Électricité, Transport...")
        self.txt_name.setMinimumHeight(34)
        self.txt_desc = QLineEdit(str((type_data or {}).get("Description") or ""))
        self.txt_desc.setPlaceholderText("Description (optionnelle)")
        self.txt_desc.setMinimumHeight(34)
        form.addRow("Nom du Type * :", self.txt_name)
        form.addRow("Description :", self.txt_desc)
        lay.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Annuler")
        apply_button_icon(btn_cancel, "close_slate", 15)
        btn_cancel.setMinimumHeight(34)
        btn_cancel.setStyleSheet(SLATE_OUTLINE_QSS)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Enregistrer")
        apply_button_icon(btn_save, "save_white", 15)
        btn_save.setMinimumHeight(34)
        btn_save.setStyleSheet(PRIMARY_CTA_QSS)
        btn_save.clicked.connect(self._on_save)

        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        lay.addLayout(btns)

    def _on_save(self):
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Champ Requis", "Veuillez saisir le nom du type de décharge.")
            self.txt_name.setFocus()
            return
        self.accept()

    def get_values(self):
        return self.txt_name.text().strip(), self.txt_desc.text().strip()


class DechargeTypesTab(QWidget):
    """CRUD workspace for Types de Décharges inside Données de Base."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._mgr = getattr(data_manager, "decharges", None)
        if self._mgr is None and getattr(data_manager, "db", None) is not None:
            self._mgr = DechargeManager(data_manager.db)
        self._rows = []
        self._init_ui()
        self.load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher un type de décharge...")
        self.search_input.setMinimumHeight(35)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filter)

        btn_add = QPushButton("Ajouter Type")
        apply_button_icon(btn_add, "plus_white", 15)
        btn_add.setMinimumHeight(35)
        btn_add.setStyleSheet(PRIMARY_CTA_QSS)
        btn_add.clicked.connect(self.open_add_dialog)

        btn_refresh = QPushButton("Actualiser")
        apply_button_icon(btn_refresh, "refresh", 15)
        btn_refresh.setMinimumHeight(35)
        btn_refresh.setStyleSheet(SLATE_OUTLINE_QSS)
        btn_refresh.clicked.connect(self.load_data)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_refresh)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 3)
        self.table.setStyleSheet(CLEAN_TABLE_QSS)
        self.table.setHorizontalHeaderLabels(["ID", "Type de Décharge", "Description"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.open_edit_dialog)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch()

        self.btn_edit = QPushButton("Modifier")
        apply_button_icon(self.btn_edit, "edit", 15)
        self.btn_edit.setMinimumHeight(34)
        self.btn_edit.setStyleSheet(SLATE_OUTLINE_QSS)
        self.btn_edit.clicked.connect(self.open_edit_dialog)

        self.btn_delete = QPushButton("Supprimer")
        apply_button_icon(self.btn_delete, "trash", 15)
        self.btn_delete.setMinimumHeight(34)
        self.btn_delete.setStyleSheet(DANGER_OUTLINE_QSS)
        self.btn_delete.clicked.connect(self.delete_selected)

        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_delete)
        layout.addLayout(actions)

    def load_data(self):
        self._rows = self._mgr.get_all_types(only_active=True) if self._mgr else []
        self._apply_filter()

    def _apply_filter(self):
        q = self.search_input.text().strip().lower()
        filtered = [
            r for r in self._rows
            if not q or q in str(r.get("Type_Name") or "").lower() or q in str(r.get("Description") or "").lower()
        ]
        self.table.setRowCount(0)
        for row_idx, r in enumerate(filtered):
            self.table.insertRow(row_idx)
            it_id = QTableWidgetItem(str(r["Type_ID"]))
            it_id.setData(Qt.UserRole, r)
            self.table.setItem(row_idx, 0, it_id)
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(r.get("Type_Name") or "")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(r.get("Description") or "")))

    def _selected_row_data(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.UserRole) if it else None

    def open_add_dialog(self):
        dlg = _DechargeTypeDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            name, desc = dlg.get_values()
            try:
                self._mgr.add_type(name, desc)
                self.load_data()
            except Exception as err:
                QMessageBox.critical(self, "Erreur", str(err))

    def open_edit_dialog(self):
        data = self._selected_row_data()
        if not data:
            QMessageBox.information(self, "Sélection", "Veuillez sélectionner un type de décharge à modifier.")
            return
        dlg = _DechargeTypeDialog(type_data=data, parent=self)
        if dlg.exec() == QDialog.Accepted:
            name, desc = dlg.get_values()
            try:
                self._mgr.update_type(int(data["Type_ID"]), name, desc, is_active=True)
                self.load_data()
            except Exception as err:
                QMessageBox.critical(self, "Erreur", str(err))

    def delete_selected(self):
        data = self._selected_row_data()
        if not data:
            QMessageBox.information(self, "Sélection", "Veuillez sélectionner un type de décharge à supprimer.")
            return
        ans = QMessageBox.question(
            self,
            "Confirmation",
            f"Supprimer le type de décharge « {data.get('Type_Name')} » ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            try:
                self._mgr.delete_type(int(data["Type_ID"]))
                self.load_data()
            except Exception as err:
                QMessageBox.critical(self, "Erreur", str(err))
