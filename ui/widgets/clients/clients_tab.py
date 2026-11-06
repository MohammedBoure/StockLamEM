# ui/widgets/master_data/clients_tab.py
# -*- coding: utf-8 -*-

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QMessageBox, QLineEdit,
    QMenu, QLabel, QFrame
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QBrush

from ui.widgets.master_data.dialogs import ClientDialog
from .client_statement_dialog import ClientStatementDialog
from .client_versements_dialog import ClientVersementsDialog
from ui.formatting import format_money
from ui.icons import get_duotone_icon

logger = logging.getLogger(__name__)


class ClientsTab(QWidget):
    """
    Dedicated workspace tab for managing clients with dynamic balance & credit limit tracking,
    account statements, and database-level Lazy Loading on scroll & pagination.
    """

    BATCH_SIZE = 50

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.client_manager = getattr(data_manager, "clients", None)

        self._current_offset = 0
        self._total_count = 0
        self._is_loading = False
        self._has_more = True
        self._loaded_ids = set()

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # --- Top Header & Toolbar Card ---
        toolbar_card = QFrame()
        toolbar_card.setObjectName("ClientsToolbarCard")
        toolbar_card.setStyleSheet("""
            QFrame#ClientsToolbarCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        t_layout = QHBoxLayout(toolbar_card)
        t_layout.setContentsMargins(14, 10, 14, 10)
        t_layout.setSpacing(10)

        # Title & Icon
        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_duotone_icon("clients", 20).pixmap(20, 20))
        t_layout.addWidget(lbl_icon)

        lbl_title = QLabel("Répertoire des Clients")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E293B;")
        t_layout.addWidget(lbl_title)

        self.lbl_counter = QLabel("0 client(s)")
        self.lbl_counter.setStyleSheet("""
            QLabel {
                background-color: #E6F4F1;
                color: #007572;
                border: 1px solid #BCE3DC;
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 700;
            }
        """)
        t_layout.addWidget(self.lbl_counter)

        t_layout.addSpacing(15)

        # Search Bar with Debounce
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher par nom, téléphone, email, ville...")
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 0 12px;
                font-size: 12px;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 1.5px solid #007572;
            }
        """)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(lambda: self.load_clients_data(reset=True))
        self.search_input.textChanged.connect(self.search_timer.start)
        t_layout.addWidget(self.search_input, 1)

        # Action Buttons
        self.add_button = QPushButton("Nouveau Client")
        self.add_button.setIcon(get_duotone_icon("add_client", 16))
        self.add_button.setIconSize(QSize(16, 16))
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setFixedHeight(36)
        self.add_button.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                padding: 0 16px;
                border-radius: 5px;
                border: 1px solid #005A57;
            }
            QPushButton:hover { background-color: #005A57; border-color: #003D3A; }
            QPushButton:pressed { background-color: #003D3A; }
        """)
        self.add_button.clicked.connect(self.open_add_dialog)
        t_layout.addWidget(self.add_button)

        self.btn_statement_top = QPushButton("Relevé de Compte")
        self.btn_statement_top.setIcon(get_duotone_icon("statement", 14))
        self.btn_statement_top.setIconSize(QSize(14, 14))
        self.btn_statement_top.setCursor(Qt.PointingHandCursor)
        self.btn_statement_top.setFixedHeight(36)
        self.btn_statement_top.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #007572;
                border: 1.5px solid #007572;
                font-weight: 700;
                font-size: 12px;
                padding: 0 14px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #E6F4F1; border-color: #005A57; color: #005A57; }
            QPushButton:pressed { background-color: #CCEBE6; }
        """)
        self.btn_statement_top.clicked.connect(self.open_statement_dialog)
        t_layout.addWidget(self.btn_statement_top)

        self.btn_versements = QPushButton("Versements")
        self.btn_versements.setIcon(get_duotone_icon("kpi_wallet", 14))
        self.btn_versements.setIconSize(QSize(14, 14))
        self.btn_versements.setCursor(Qt.PointingHandCursor)
        self.btn_versements.setFixedHeight(36)
        self.btn_versements.setToolTip("Consulter l'historique des versements et le solde portefeuille du client")
        self.btn_versements.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #007572;
                border: 1.5px solid #007572;
                font-weight: 700;
                font-size: 12px;
                padding: 0 14px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #E6F4F1; border-color: #005A57; color: #005A57; }
            QPushButton:pressed { background-color: #CCEBE6; }
        """)
        self.btn_versements.clicked.connect(self.open_versements_dialog)
        t_layout.addWidget(self.btn_versements)

        self.refresh_button = QPushButton("Actualiser")
        self.refresh_button.setIcon(get_duotone_icon("refresh", 14))
        self.refresh_button.setIconSize(QSize(14, 14))
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setFixedHeight(36)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1.5px solid #CBD5E1;
                font-weight: 700;
                font-size: 12px;
                padding: 0 14px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #F1F5F9; border-color: #94A3B8; color: #1E293B; }
            QPushButton:pressed { background-color: #E2E8F0; }
        """)
        self.refresh_button.clicked.connect(lambda: self.load_clients_data(reset=True))
        t_layout.addWidget(self.refresh_button)

        main_layout.addWidget(toolbar_card)

        # --- Table Widget with Dense Data & Lazy Loading on Scroll ---
        self.clients_table = QTableWidget()
        columns = [
            "ID", "Nom du Client", "Contact", "Téléphone", "Email",
            "Ville", "Catégorie", "Plafond Crédit", "Solde Actuel", "NIF", "RC"
        ]
        self.clients_table.setColumnCount(len(columns))
        self.clients_table.setHorizontalHeaderLabels(columns)

        self.clients_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                gridline-color: #E2E8F0;
                selection-background-color: #E6F4F1;
                selection-color: #0F172A;
                alternate-background-color: #F8FAFC;
            }
            QTableWidget::item:selected {
                background-color: #E6F4F1;
                color: #0F172A;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 700;
                font-size: 12px;
                padding: 7px 10px;
                border: none;
                border-bottom: 2px solid #007572;
                border-right: 1px solid #E2E8F0;
            }
            QScrollBar:vertical {
                border: none;
                background: #F8FAFC;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #007572;
            }
            QScrollBar:horizontal {
                border: none;
                background: #F8FAFC;
                height: 8px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #CBD5E1;
                min-width: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #007572;
            }
        """)

        self.clients_table.setSortingEnabled(True)
        self.clients_table.horizontalHeader().setSectionsClickable(True)
        self.clients_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.clients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.clients_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.clients_table.setAlternatingRowColors(True)
        self.clients_table.verticalHeader().setDefaultSectionSize(38)
        self.clients_table.verticalHeader().setVisible(False)
        self.clients_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.clients_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.clients_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

        self.clients_table.setColumnHidden(0, True)  # Hide ID

        self.clients_table.doubleClicked.connect(self.open_edit_dialog)
        self.clients_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.clients_table.customContextMenuRequested.connect(self.open_context_menu)

        # Lazy Loading trigger on scroll
        self.clients_table.verticalScrollBar().valueChanged.connect(self._on_table_scroll)

        main_layout.addWidget(self.clients_table, 1)

        # --- Bottom Status & Actions Bar ---
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(4, 2, 4, 2)
        actions_layout.setSpacing(10)

        self.lbl_lazy_status = QLabel("Chargement initial des clients...")
        self.lbl_lazy_status.setStyleSheet("font-size: 12px; color: #64748B; font-weight: 600;")
        actions_layout.addWidget(self.lbl_lazy_status)

        self.btn_load_more = QPushButton("Charger plus de clients...")
        self.btn_load_more.setCursor(Qt.PointingHandCursor)
        self.btn_load_more.setFixedHeight(30)
        self.btn_load_more.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                color: #007572;
                border: 1px dashed #007572;
                font-weight: 700;
                font-size: 11px;
                padding: 0 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #E6F4F1; }
        """)
        self.btn_load_more.clicked.connect(self.load_more_clients)
        self.btn_load_more.setVisible(False)
        actions_layout.addWidget(self.btn_load_more)

        actions_layout.addStretch()

        self.statement_button = QPushButton("Relevé de Compte")
        self.statement_button.setIcon(get_duotone_icon("statement", 13))
        self.statement_button.setIconSize(QSize(13, 13))
        self.statement_button.setCursor(Qt.PointingHandCursor)
        self.statement_button.setFixedHeight(34)
        self.statement_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #007572;
                border: 1.5px solid #007572;
                font-weight: 700;
                font-size: 11px;
                padding: 0 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #E6F4F1; border-color: #005A57; color: #005A57; }
        """)
        self.statement_button.clicked.connect(self.open_statement_dialog)
        actions_layout.addWidget(self.statement_button)

        self.edit_button = QPushButton("Modifier")
        self.edit_button.setIcon(get_duotone_icon("edit", 13))
        self.edit_button.setIconSize(QSize(13, 13))
        self.edit_button.setCursor(Qt.PointingHandCursor)
        self.edit_button.setFixedHeight(34)
        self.edit_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #334155;
                border: 1px solid #CBD5E1;
                font-weight: 700;
                font-size: 11px;
                padding: 0 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #F8FAFC; border-color: #94A3B8; color: #0F172A; }
        """)
        self.edit_button.clicked.connect(self.open_edit_dialog)
        actions_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setIcon(get_duotone_icon("trash", 13))
        self.delete_button.setIconSize(QSize(13, 13))
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setFixedHeight(34)
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #DC2626;
                border: 1px solid #FECACA;
                font-weight: 700;
                font-size: 11px;
                padding: 0 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #FEF2F2; border-color: #DC2626; }
        """)
        self.delete_button.clicked.connect(self.delete_client)
        actions_layout.addWidget(self.delete_button)

        main_layout.addLayout(actions_layout)

        # Initial Lazy Load
        self.load_clients_data(reset=True)

    def _create_centered_item(self, text, is_numeric=False):
        item = QTableWidgetItem()
        if is_numeric:
            try:
                val = float(str(text))
                item.setData(Qt.EditRole, val)
            except Exception:
                item.setText(str(text))
        else:
            item.setText(str(text) if text is not None else "")
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _on_table_scroll(self, value):
        """Triggers next batch loading when user scrolls within 3 rows of the bottom."""
        sb = self.clients_table.verticalScrollBar()
        if sb.maximum() > 0 and value >= sb.maximum() - 3:
            if not self._is_loading and self._has_more:
                self.load_more_clients()

    def load_clients_data(self, reset=True):
        """Loads client data via Lazy Loading."""
        if reset:
            self._current_offset = 0
            self._has_more = True
            self._loaded_ids.clear()
            self.clients_table.setRowCount(0)

        self.load_more_clients()

    def load_more_clients(self):
        """Loads the next chunk of clients and appends them to the table."""
        if self._is_loading or not self._has_more:
            return

        self._is_loading = True
        search_text = self.search_input.text().strip()

        try:
            if self.client_manager and hasattr(self.client_manager, "get_clients_paged"):
                res = self.client_manager.get_clients_paged(
                    search_text=search_text,
                    offset=self._current_offset,
                    limit=self.BATCH_SIZE
                )
            else:
                # Fallback if get_clients_paged is not directly provided
                if hasattr(self.client_manager, 'get_all_clients_with_balances'):
                    all_c = self.client_manager.get_all_clients_with_balances()
                elif hasattr(self.client_manager, 'get_all_clients'):
                    all_c = self.client_manager.get_all_clients()
                else:
                    all_c = []

                if search_text:
                    st = search_text.lower()
                    filtered = [
                        c for c in all_c
                        if st in str(c.get('Client_Name', '')).lower()
                        or (c.get('Email') and st in str(c.get('Email', '')).lower())
                        or (c.get('City') and st in str(c.get('City', '')).lower())
                        or (c.get('Phone') and st in str(c.get('Phone', '')).lower())
                        or (c.get('Price_Tier') and st in str(c.get('Price_Tier', '')).lower())
                        or (c.get('Contact_Person') and st in str(c.get('Contact_Person', '')).lower())
                    ]
                else:
                    filtered = all_c

                tot = len(filtered)
                chunk = filtered[self._current_offset:self._current_offset + self.BATCH_SIZE]
                res = {
                    "items": chunk,
                    "total_count": tot,
                    "has_more": (self._current_offset + len(chunk)) < tot
                }

            if isinstance(res, dict):
                items = res.get("items", [])
                raw_tot = res.get("total_count", 0)
            else:
                items = []
                raw_tot = 0

            try:
                self._total_count = int(raw_tot)
            except (TypeError, ValueError):
                self._total_count = len(items)

            # Append rows
            self._append_client_rows(items)

            self._current_offset += len(items)
            self._has_more = (self._current_offset < self._total_count) and len(items) > 0

            # Update counter & status
            loaded_count = self.clients_table.rowCount()
            self.lbl_counter.setText(f"{loaded_count} / {self._total_count} client{'s' if self._total_count > 1 else ''}")

            if self._has_more:
                self.lbl_lazy_status.setText(f"Affichage de {loaded_count} sur {self._total_count} clients (défilez pour charger la suite)")
                self.btn_load_more.setVisible(True)
            else:
                self.lbl_lazy_status.setText(f"Tous les clients sont affichés ({loaded_count} clients au total)")
                self.btn_load_more.setVisible(False)

        except Exception as e:
            logger.error(f"Error lazy loading clients: {e}", exc_info=True)
            self.lbl_lazy_status.setText(f"Erreur de chargement: {str(e)}")
        finally:
            self._is_loading = False

    def _append_client_rows(self, clients_batch):
        """Appends a batch of client records to the table."""
        self.clients_table.setSortingEnabled(False)

        tier_map = {
            'Prix_1': 'Prix 1 (Détail)',
            'Prix_2': 'Prix 2 (Demi-Gros)',
            'Prix_3': 'Prix 3 (Gros)',
            'Prix_4': 'Prix 4 (Super-Gros)'
        }

        for c in clients_batch:
            cid = c.get('Client_ID')
            if cid in self._loaded_ids:
                continue
            self._loaded_ids.add(cid)

            row_idx = self.clients_table.rowCount()
            self.clients_table.insertRow(row_idx)

            # 0. ID
            self.clients_table.setItem(row_idx, 0, self._create_centered_item(cid, is_numeric=True))

            # 1. Nom du Client
            it_name = QTableWidgetItem(str(c.get('Client_Name') or ''))
            it_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.clients_table.setItem(row_idx, 1, it_name)

            # 2. Contact
            self.clients_table.setItem(row_idx, 2, self._create_centered_item(c.get('Contact_Person', '')))

            # 3. Téléphone
            self.clients_table.setItem(row_idx, 3, self._create_centered_item(c.get('Phone', '')))

            # 4. Email
            self.clients_table.setItem(row_idx, 4, self._create_centered_item(c.get('Email', '')))

            # 5. Ville
            self.clients_table.setItem(row_idx, 5, self._create_centered_item(c.get('City', '')))

            # 6. Catégorie (Price_Tier)
            raw_tier = str(c.get('Price_Tier') or 'Prix_1')
            item_tier = self._create_centered_item(tier_map.get(raw_tier, raw_tier))
            self.clients_table.setItem(row_idx, 6, item_tier)

            # 7. Plafond Crédit
            limit_val = float(c.get('Credit_Limit') or 0.0)
            item_limit = QTableWidgetItem(f"{format_money(limit_val)} DA" if limit_val > 0 else "Illimité")
            item_limit.setData(Qt.EditRole, limit_val)
            item_limit.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.clients_table.setItem(row_idx, 7, item_limit)

            # 8. Solde Actuel avec Badge Pastel
            bal_val = float(c.get('Current_Balance') or 0.0)
            item_bal = QTableWidgetItem(f"{format_money(bal_val)} DA")
            item_bal.setData(Qt.EditRole, bal_val)
            item_bal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_bal.setFont(QFont("Segoe UI", 9, QFont.Bold))

            # Soft pastel green if Solde <= Limit, soft pastel red if exceeding limit
            if limit_val > 0 and bal_val > limit_val:
                item_bal.setBackground(QBrush(QColor("#FEE2E2")))
                item_bal.setForeground(QBrush(QColor("#DC2626")))
            elif bal_val > 0:
                item_bal.setBackground(QBrush(QColor("#FEF3C7")))
                item_bal.setForeground(QBrush(QColor("#D97706")))
            else:
                item_bal.setBackground(QBrush(QColor("#DCFCE7")))
                item_bal.setForeground(QBrush(QColor("#16A34A")))

            self.clients_table.setItem(row_idx, 8, item_bal)

            # 9. NIF & 10. RC
            self.clients_table.setItem(row_idx, 9, self._create_centered_item(c.get('Tax_ID_Number', '')))
            self.clients_table.setItem(row_idx, 10, self._create_centered_item(c.get('Commercial_Reg_No', '')))

        self.clients_table.setSortingEnabled(True)

    def open_add_dialog(self):
        dialog = ClientDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                res = self.client_manager.add_client(**data)
                if res:
                    self.load_clients_data(reset=True)
                else:
                    QMessageBox.warning(self, "Erreur", "Ce nom de client existe déjà ou une erreur est survenue.")

    def open_edit_dialog(self):
        row = self.clients_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client à modifier.")
            return

        client_id_item = self.clients_table.item(row, 0)
        if not client_id_item:
            return
        client_id = int(client_id_item.text())

        client_data = self.client_manager.get_client_by_id(client_id)
        if not client_data:
            QMessageBox.warning(self, "Erreur", "Données introuvables.")
            return

        dialog = ClientDialog(self, client_data)
        if dialog.exec():
            new_data = dialog.get_data()
            if new_data:
                if self.client_manager.update_client(client_id, **new_data):
                    self.load_clients_data(reset=True)
                else:
                    QMessageBox.warning(self, "Erreur", "Impossible de mettre à jour le client.")

    def delete_client(self):
        row = self.clients_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client à supprimer.")
            return

        client_id = int(self.clients_table.item(row, 0).text())
        client_name = self.clients_table.item(row, 1).text()

        confirm = QMessageBox.question(
            self,
            "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer le client « {client_name} » ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            if self.client_manager.soft_delete_client(client_id):
                self.load_clients_data(reset=True)
            else:
                QMessageBox.warning(
                    self,
                    "Erreur",
                    "Impossible de supprimer le client. Il est peut-être associé à des factures ou opérations existantes."
                )

    def open_statement_dialog(self):
        row = self.clients_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client pour afficher son relevé de compte.")
            return

        client_id_item = self.clients_table.item(row, 0)
        if not client_id_item:
            return
        client_id = int(client_id_item.text())

        dialog = ClientStatementDialog(self.data_manager, client_id, self)
        dialog.exec()

    def open_versements_dialog(self):
        client_id = None
        row = self.clients_table.currentRow()
        if row >= 0:
            client_id_item = self.clients_table.item(row, 0)
            if client_id_item:
                try:
                    client_id = int(client_id_item.text())
                except ValueError:
                    client_id = None
        dialog = ClientVersementsDialog(self.data_manager, client_id=client_id, parent=self)
        dialog.exec()

    def open_context_menu(self, pos):
        item = self.clients_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        self.clients_table.selectRow(row)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                padding: 4px;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
                font-size: 12px;
                color: #1E293B;
            }
            QMenu::item:selected {
                background-color: #007572;
                color: #FFFFFF;
            }
        """)

        act_statement = QAction("Relevé de Compte", self)
        act_statement.setIcon(get_duotone_icon("statement", 14))
        act_statement.triggered.connect(self.open_statement_dialog)

        act_versements = QAction("Versements & Solde", self)
        act_versements.setIcon(get_duotone_icon("kpi_wallet", 14))
        act_versements.triggered.connect(self.open_versements_dialog)

        act_edit = QAction("Modifier le Client", self)
        act_edit.setIcon(get_duotone_icon("edit", 14))
        act_edit.triggered.connect(self.open_edit_dialog)

        act_delete = QAction("Supprimer le Client", self)
        act_delete.setIcon(get_duotone_icon("trash", 14))
        act_delete.triggered.connect(self.delete_client)

        menu.addAction(act_statement)
        menu.addAction(act_versements)
        menu.addSeparator()
        menu.addAction(act_edit)
        menu.addAction(act_delete)

        menu.exec(self.clients_table.viewport().mapToGlobal(pos))
