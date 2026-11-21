# ui/widgets/master_data/caisses_tab.py

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QMessageBox, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
from .dialogs import CaisseDialog


class CaissesTab(QWidget):
    """
    Onglet d'administration et de controle des caisses (Terminaux POS) dans les Donnees de Base.
    Permet la creation, modification, activation/desactivation et suivi du nombre de sessions par caisse.
    """

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.terminals_manager = data_manager.pos_terminals
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # --- Barre d'outils (Toolbar) ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher une caisse (Code, Nom)...")
        self.search_input.setMinimumHeight(36)
        self.search_input.textChanged.connect(self.filter_table)

        btn_add = QPushButton("Ajouter Caisse")
        btn_add.setMinimumHeight(36)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #007572; color: white; font-weight: bold;
                border-radius: 4px; padding: 6px 18px; border: none; font-size: 13px;
            }
            QPushButton:hover { background-color: #005a57; }
        """)
        btn_add.clicked.connect(self.open_add_dialog)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setMinimumHeight(36)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #2c3e50; border: 1px solid #cbd5e1;
                border-radius: 4px; padding: 6px 16px; font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_refresh.clicked.connect(self.load_data)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_refresh)
        layout.addLayout(toolbar)

        # --- Tableau des Caisses ---
        self.table = QTableWidget()
        cols = ["ID", "Code Caisse", "Nom de la Caisse", "Statut", "Sessions Enregistrees", "Session Active ?", "Date de Creation"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnHidden(0, True)

        self.table.doubleClicked.connect(self.open_edit_dialog)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.table)

        # --- Actions Inferieures ---
        actions = QHBoxLayout()
        actions.setSpacing(10)

        from ui.theme_tokens import (
            SLATE_OUTLINE_QSS, DANGER_OUTLINE_QSS, TEXT_MUTED, set_enabled_with_reason,
        )
        self.btn_edit = QPushButton("Modifier la Caisse")
        self.btn_edit.setMinimumHeight(34)
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setStyleSheet(SLATE_OUTLINE_QSS)
        set_enabled_with_reason(self.btn_edit, False, "Sélectionnez une caisse dans le tableau pour modifier.")
        self.btn_edit.clicked.connect(self.open_edit_dialog)

        self.btn_toggle_active = QPushButton("Activer / Desactiver")
        self.btn_toggle_active.setMinimumHeight(34)
        self.btn_toggle_active.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_active.setStyleSheet(SLATE_OUTLINE_QSS)
        set_enabled_with_reason(self.btn_toggle_active, False, "Sélectionnez une caisse dans le tableau pour changer son statut.")
        self.btn_toggle_active.clicked.connect(self.toggle_active)

        self.btn_delete = QPushButton("Supprimer")
        self.btn_delete.setMinimumHeight(34)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet(DANGER_OUTLINE_QSS)
        set_enabled_with_reason(self.btn_delete, False, "Sélectionnez une caisse dans le tableau pour supprimer.")
        self.btn_delete.clicked.connect(self.delete_caisse)

        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_toggle_active)
        actions.addWidget(self.btn_delete)
        actions.addStretch()

        self.lbl_count = QLabel("Total: 0 caisse(s)")
        self.lbl_count.setStyleSheet(f"font-weight: 700; color: {TEXT_MUTED};")
        actions.addWidget(self.lbl_count)

        layout.addLayout(actions)

    def load_data(self):
        try:
            self.raw_data = self.terminals_manager.get_all_terminals(include_inactive=True)
            self.filter_table()
        except Exception as e:
            logging.error(f"Error loading terminals: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Impossible de charger les caisses : {e}")

    def filter_table(self):
        query = self.search_input.text().strip().lower()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        filtered = []
        for t in getattr(self, 'raw_data', []):
            code = str(t.get('Terminal_Code', '')).lower()
            name = str(t.get('Terminal_Name', '')).lower()
            if not query or query in code or query in name:
                filtered.append(t)

        for row_idx, t in enumerate(filtered):
            self.table.insertRow(row_idx)

            id_item = QTableWidgetItem(str(t.get('Terminal_ID')))
            id_item.setData(Qt.UserRole, t)
            self.table.setItem(row_idx, 0, id_item)

            code_item = QTableWidgetItem(str(t.get('Terminal_Code', '')))
            code_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            code_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, code_item)

            name_item = QTableWidgetItem(str(t.get('Terminal_Name', '')))
            self.table.setItem(row_idx, 2, name_item)

            is_active = bool(t.get('Is_Active'))
            status_item = QTableWidgetItem("Active" if is_active else "Inactive")
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QBrush(QColor("#27ae60" if is_active else "#c0392b")))
            status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row_idx, 3, status_item)

            sess_cnt = t.get('Total_Sessions', 0)
            sess_item = QTableWidgetItem(str(sess_cnt))
            sess_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, sess_item)

            has_open = bool(t.get('Has_Open_Session'))
            open_item = QTableWidgetItem("En cours (Ouverte)" if has_open else "---")
            open_item.setTextAlignment(Qt.AlignCenter)
            if has_open:
                open_item.setForeground(QBrush(QColor("#007572")))
                open_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row_idx, 5, open_item)

            created = str(t.get('Created_At', '---'))[:19]
            date_item = QTableWidgetItem(created)
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 6, date_item)

        self.table.setSortingEnabled(True)
        self.lbl_count.setText(f"Total: {len(filtered)} caisse(s)")
        self.on_selection_changed()

    def get_selected_data(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.UserRole)
        return None

    def on_selection_changed(self):
        from ui.theme_tokens import set_enabled_with_reason
        has_sel = self.get_selected_data() is not None
        set_enabled_with_reason(self.btn_edit, has_sel, "Sélectionnez une caisse dans le tableau pour modifier.", "Modifier la caisse sélectionnée")
        set_enabled_with_reason(self.btn_toggle_active, has_sel, "Sélectionnez une caisse dans le tableau pour changer son statut.", "Activer ou désactiver la caisse sélectionnée")
        set_enabled_with_reason(self.btn_delete, has_sel, "Sélectionnez une caisse dans le tableau pour supprimer.", "Supprimer la caisse sélectionnée")

    def open_add_dialog(self):
        dlg = CaisseDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            if not data:
                return
            success, msg, _ = self.terminals_manager.add_terminal(
                terminal_code=data['terminal_code'],
                terminal_name=data['terminal_name'],
                is_active=data['is_active']
            )
            if success:
                QMessageBox.information(self, "Succes", msg)
                self.load_data()
            else:
                QMessageBox.warning(self, "Attention", msg)

    def open_edit_dialog(self):
        caisse = self.get_selected_data()
        if not caisse:
            return
        dlg = CaisseDialog(parent=self, data=caisse)
        if dlg.exec():
            data = dlg.get_data()
            if not data:
                return
            success, msg = self.terminals_manager.update_terminal(
                terminal_id=caisse['Terminal_ID'],
                terminal_code=data['terminal_code'],
                terminal_name=data['terminal_name'],
                is_active=data['is_active']
            )
            if success:
                QMessageBox.information(self, "Succes", msg)
                self.load_data()
            else:
                QMessageBox.warning(self, "Attention", msg)

    def toggle_active(self):
        caisse = self.get_selected_data()
        if not caisse:
            return
        terminal_id = caisse['Terminal_ID']
        success, msg, _ = self.terminals_manager.toggle_terminal_active(terminal_id)
        if success:
            self.load_data()
        else:
            QMessageBox.warning(self, "Attention", msg)

    def delete_caisse(self):
        caisse = self.get_selected_data()
        if not caisse:
            return
        terminal_id = caisse['Terminal_ID']
        code = caisse.get('Terminal_Code', '')

        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous vraiment supprimer la caisse '{code}' ?`n`n"
            "Si des sessions de caisse ou des ventes y sont deja rattachees, la caisse sera automatiquement desactivee pour preserver l'historique.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = self.terminals_manager.delete_terminal(terminal_id)
            if success:
                QMessageBox.information(self, "Information", msg)
                self.load_data()
            else:
                QMessageBox.warning(self, "Attention", msg)
