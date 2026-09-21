# ui/widgets/sales_history/sales_history_tab.py

import csv
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QHeaderView, QPushButton,
    QHBoxLayout, QLabel, QComboBox, QDateEdit, QDialog,
    QAbstractItemView, QTableWidgetItem, QMessageBox,
    QFileDialog, QFrame, QSizePolicy, QCheckBox, QMenu
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QFont

from ui.widgets.inventory.dialogs import BarcodeLineEdit
from ui.formatting import format_money, format_quantity
from ui.widgets.sales.invoice_payment_dialog import InvoicePaymentDialog
from ui.widgets.sales.return_dialog import ReturnProductSelectionDialog
from ui.widgets.sales.searchable_client_combo import SearchableClientComboBox
from .sale_details_dialog import SaleDetailsDialog
from .pdf_export import export_invoice_to_pdf


class SalesHistoryTab(QWidget):
    """
    Interface d'historique général des ventes, factures et sessions de caisse.
    Permet le filtrage multi-critères, le suivi des impayés et du vieillissement de la dette (AR Aging),
    l'encaissement de règlements, l'annulation et la consultation détaillée.
    """

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.can_view_profit = self._has_permission("act_pos_view_profit")
        self.raw_data = []
        self.filtered_data = []
        self.current_offset = 0
        self.batch_size = 50
        self.is_loading = False
        self.has_more_data = True
        self.init_ui()
        self.load_filters()
        self.load_sales_data()

    def _has_permission(self, permission):
        checker = getattr(self.window(), "has_permission", None)
        if callable(checker):
            return bool(checker(permission))
        return True

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        # --- 1. Filter Section (Responsive 2-Tier Container) ---
        filter_frame = QFrame()
        filter_frame.setObjectName("SalesHistoryFilterFrame")
        filter_frame.setStyleSheet("""
            QFrame#SalesHistoryFilterFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QLabel {
                color: #334155;
                font-weight: 600;
                font-size: 12px;
            }
            QComboBox, QDateEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 12px;
                min-height: 28px;
            }
            QComboBox:focus, QDateEdit:focus {
                border-color: #007572;
            }
        """)
        filter_vbox = QVBoxLayout(filter_frame)
        filter_vbox.setContentsMargins(4, 4, 4, 4)
        filter_vbox.setSpacing(8)

        # Tier 1: Period & Primary Filters
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(8)
        row1_layout.setContentsMargins(0, 0, 0, 0)

        lbl_from = QLabel("📅 Du :")
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setFixedWidth(105)
        self.date_from.dateChanged.connect(self.apply_filter_local)

        lbl_to = QLabel("au :")
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setFixedWidth(105)
        self.date_to.dateChanged.connect(self.apply_filter_local)

        lbl_caisse = QLabel("🏦 Caisse :")
        self.cb_caisse = QComboBox()
        self.cb_caisse.addItem("Toutes les Caisses", None)
        self.cb_caisse.setMinimumWidth(130)
        self.cb_caisse.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.cb_caisse.currentIndexChanged.connect(self.apply_filter_local)

        lbl_client = QLabel("👤 Client :")
        self.cb_client = SearchableClientComboBox(self, placeholder="🔍 Tous les Clients (Nom/Tél)...")
        self.cb_client.setMinimumWidth(200)
        self.cb_client.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.cb_client.client_changed.connect(lambda _: self.load_sales_data())

        lbl_status = QLabel("Statut :")
        self.cb_status = QComboBox()
        self.cb_status.addItem("Tous les statuts", None)
        for status in ("Validated", "Paid", "Cancelled"):
            self.cb_status.addItem(status, status)
        self.cb_status.setMinimumWidth(110)
        self.cb_status.currentIndexChanged.connect(self.apply_filter_local)

        lbl_payment = QLabel("Paiement :")
        self.cb_payment = QComboBox()
        self.cb_payment.addItem("Tous les paiements", None)
        for method, label in (("Cash", "Espèces"), ("Card", "Carte"), ("Transfer", "Virement"), ("Versement", "Versement"), ("Other", "Autre"), ("Credit", "Crédit")):
            self.cb_payment.addItem(label, method)
        self.cb_payment.setMinimumWidth(110)
        self.cb_payment.currentIndexChanged.connect(self.apply_filter_local)

        btn_refresh = QPushButton("🔄 Actualiser")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setToolTip("Actualiser les données de vente (F5)")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #007572; border: 1px solid #cbd5e1;
                border-radius: 4px; padding: 4px 12px; min-height: 28px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #e6f4f1; border-color: #007572; }
        """)
        btn_refresh.clicked.connect(self.load_sales_data)

        row1_layout.addWidget(lbl_from)
        row1_layout.addWidget(self.date_from)
        row1_layout.addWidget(lbl_to)
        row1_layout.addWidget(self.date_to)
        row1_layout.addWidget(lbl_caisse)
        row1_layout.addWidget(self.cb_caisse)
        row1_layout.addWidget(lbl_client)
        row1_layout.addWidget(self.cb_client)
        row1_layout.addWidget(lbl_status)
        row1_layout.addWidget(self.cb_status)
        row1_layout.addWidget(lbl_payment)
        row1_layout.addWidget(self.cb_payment)

        # AR Aging Controls
        self.chk_overdue_only = QCheckBox("⚠️ Factures Échues Non Payées")
        self.chk_overdue_only.setToolTip("Filtrer uniquement les factures échues non payées / non soldées")
        self.chk_overdue_only.setStyleSheet("color: #dc2626; font-weight: bold; font-size: 12px;")

        self.cb_aging = QComboBox()
        self.cb_aging.addItem("Toutes Échues", "all")
        self.cb_aging.addItem("0 - 30 jours", "0-30")
        self.cb_aging.addItem("31 - 60 jours", "31-60")
        self.cb_aging.addItem("> 60 jours", ">60")
        self.cb_aging.setEnabled(False)
        self.cb_aging.setFixedWidth(115)
        self.chk_overdue_only.toggled.connect(lambda checked: (self.cb_aging.setEnabled(checked), self.apply_filter_local()))
        self.cb_aging.currentIndexChanged.connect(self.apply_filter_local)

        row1_layout.addWidget(self.chk_overdue_only)
        row1_layout.addWidget(self.cb_aging)
        row1_layout.addStretch(1)
        row1_layout.addWidget(btn_refresh)

        filter_vbox.addLayout(row1_layout)

        # Tier 2: Search Input & Action Buttons
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(8)
        row2_layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = BarcodeLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher par ID, N° Facture, Client, Caisse ou Utilisateur...")
        self.search_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                min-height: 30px;
            }
            QLineEdit:focus {
                border: 2px solid #007572;
            }
        """)
        self.search_input.textChanged.connect(self.apply_filter_local)
        row2_layout.addWidget(self.search_input, stretch=1)

        self.btn_settle_payment = QPushButton("💳 Encaisser Paiement")
        self.btn_settle_payment.setEnabled(False)
        self.btn_settle_payment.setCursor(Qt.PointingHandCursor)
        self.btn_settle_payment.setStyleSheet("""
            QPushButton {
                background-color: #0f766e; color: white; font-weight: bold;
                border-radius: 4px; padding: 4px 14px; min-height: 30px; border: none; font-size: 12px;
            }
            QPushButton:hover { background-color: #115e59; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        self.btn_settle_payment.clicked.connect(self._open_payment_settlement)

        self.btn_print_selected = QPushButton("🖨️ Imprimer Facture")
        self.btn_print_selected.setEnabled(False)
        self.btn_print_selected.setCursor(Qt.PointingHandCursor)
        self.btn_print_selected.setStyleSheet("""
            QPushButton {
                background-color: #007572; color: white; font-weight: bold;
                border-radius: 4px; padding: 4px 14px; min-height: 30px; border: none; font-size: 12px;
            }
            QPushButton:hover { background-color: #005a57; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        self.btn_print_selected.clicked.connect(self.print_selected_invoice)

        self.btn_no_invoice_return = QPushButton("↩️ Retour sans facture")
        self.btn_no_invoice_return.setCursor(Qt.PointingHandCursor)
        self.btn_no_invoice_return.setStyleSheet("""
            QPushButton {
                background-color: #fff7ed; color: #c2410c; border: 1px solid #fdba74;
                border-radius: 4px; padding: 4px 14px; min-height: 30px; font-weight: 600; font-size: 12px;
            }
            QPushButton:hover { background-color: #ffedd5; border-color: #ea580c; }
        """)
        self.btn_no_invoice_return.clicked.connect(self.create_no_invoice_return)

        self.btn_export = QPushButton("📥 Exporter CSV")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #334155; border: 1px solid #cbd5e1;
                border-radius: 4px; padding: 4px 14px; min-height: 30px; font-weight: 600; font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_export.clicked.connect(self.export_filtered_csv)

        row2_layout.addWidget(self.btn_settle_payment)
        row2_layout.addWidget(self.btn_print_selected)
        row2_layout.addWidget(self.btn_no_invoice_return)
        row2_layout.addWidget(self.btn_export)

        filter_vbox.addLayout(row2_layout)

        layout.addWidget(filter_frame)

        # --- 2. Table Section ---
        self.table = QTableWidget()
        cols = [
            "ID", "Date", "Operation", "Client / Details", "Statut",
            "Retard (Jours)", "Caisse", "Utilisateur", "Paiement", "Montant saisi",
            "Total TTC", "Fayda (Profit)", "Action"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setColumnHidden(11, not self.can_view_profit)

        f = self.table.font()
        f.setPointSize(9)
        self.table.setFont(f)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(12, QHeaderView.ResizeToContents)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self.show_full_details)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)

        layout.addWidget(self.table)

        # --- 3. Bottom Status & Summary Bar (Single thin line) ---
        bottom_bar = QFrame()
        bottom_bar.setObjectName("SalesHistoryBottomBar")
        bottom_bar.setFixedHeight(34)
        bottom_bar.setStyleSheet("""
            QFrame#SalesHistoryBottomBar {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 0px 6px;
            }
            QLabel {
                font-size: 12px;
                font-weight: 600;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(6, 2, 6, 2)
        bottom_layout.setSpacing(10)

        # 1. Lazy loading status indicator (like Traçabilité)
        self.lbl_status = QLabel("0/0")
        self.lbl_status.setToolTip("Enregistrements affichés / Total filtré")
        self.lbl_status.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 12px;
                color: #334155;
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
            }
        """)
        bottom_layout.addWidget(self.lbl_status)

        bottom_layout.addStretch(1)

        # 2. Number of sales operations
        self.lbl_sales_count = QLabel("Ventes : 0")
        self.lbl_sales_count.setToolTip("Nombre d'opérations de vente de la période")
        self.lbl_sales_count.setStyleSheet("""
            QLabel {
                color: #0f172a;
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
            }
        """)
        bottom_layout.addWidget(self.lbl_sales_count)

        # 3. Total money that went out (purchase cost of goods sold)
        self.lbl_total_cost = QLabel("Coût Achat : 0.00 DA")
        self.lbl_total_cost.setToolTip("Total sorties au prix d'achat des produits vendus")
        self.lbl_total_cost.setStyleSheet("""
            QLabel {
                color: #c2410c;
                background-color: #fff7ed;
                border: 1px solid #fed7aa;
                border-radius: 4px;
                padding: 2px 8px;
            }
        """)
        bottom_layout.addWidget(self.lbl_total_cost)

        # 4. Total money that came in (total sales revenue TTC)
        self.lbl_total_sales = QLabel("Total Ventes : 0.00 DA")
        self.lbl_total_sales.setToolTip("Total entrées / Chiffre d'affaires des ventes TTC")
        self.lbl_total_sales.setStyleSheet("""
            QLabel {
                color: #1d4ed8;
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                padding: 2px 8px;
            }
        """)
        bottom_layout.addWidget(self.lbl_total_sales)

        # 5. Total net profit / interest (bénéfice / intérêt)
        self.lbl_total_period_profit = QLabel("Bénéfice : 0.00 DA")
        self.lbl_total_period_profit.setObjectName("ProfitLabel")
        self.lbl_total_period_profit.setToolTip("Marge bénéficiaire nette de la période")
        self.lbl_total_period_profit.setStyleSheet("""
            QLabel {
                color: #047857;
                background-color: #ecfdf5;
                border: 1px solid #a7f3d0;
                border-radius: 4px;
                padding: 2px 8px;
            }
        """)
        bottom_layout.addWidget(self.lbl_total_period_profit)

        if not self.can_view_profit:
            self.lbl_total_cost.setText("Coût Achat : accès restreint")
            self.lbl_total_period_profit.setText("Bénéfice : accès restreint")

        layout.addWidget(bottom_bar)

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        inv = id_item.data(Qt.UserRole)
        if not inv:
            return

        menu = QMenu(self)
        if inv.get('Row_Type') == 'Sale':
            action_settle = menu.addAction("💳 Encaisser Paiement")
            total_ttc = float(inv.get('Total_Amount_TTC') or 0.0)
            paid_amount = float(inv.get('Paid_Amount') or 0.0)
            can_settle = (inv.get('Status') != 'Cancelled' and (total_ttc - paid_amount > 0.01))
            action_settle.setEnabled(can_settle)
            action_settle.triggered.connect(lambda: self._open_payment_settlement(inv))

            action_details = menu.addAction("🔍 Voir Détails de la Vente")
            action_details.triggered.connect(self.show_full_details)

            action_print = menu.addAction("🖨️ Imprimer Facture")
            action_print.triggered.connect(self.print_selected_invoice)
        elif inv.get('Row_Type') in ('Cash_Open', 'Cash_Close'):
            action_details = menu.addAction("🔍 Détails de Session Caisse")
            action_details.triggered.connect(self.show_full_details)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _open_payment_settlement(self, inv=None):
        if not inv or not isinstance(inv, dict):
            row = self.table.currentRow()
            if row >= 0 and self.table.item(row, 0):
                inv = self.table.item(row, 0).data(Qt.UserRole)
        if not inv or inv.get('Row_Type') != 'Sale':
            return

        dlg = InvoicePaymentDialog(self.data_manager, inv, self)
        if dlg.exec() == QDialog.Accepted:
            self.load_sales_data()

    def create_no_invoice_return(self):
        checker = getattr(self.window(), "has_permission", None)
        if checker and not checker("act_pos_return_without_invoice"):
            QMessageBox.warning(self, "Autorisation", "Le retour sans facture est réservé au manager.")
            return

        dlg = ReturnProductSelectionDialog(self.data_manager, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.load_sales_data()

    def _current_user_id(self):
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return None

    def load_filters(self):
        clients = self.data_manager.clients.get_all_clients()
        self.cb_client.set_clients(clients)

        if hasattr(self, 'cb_caisse'):
            self.cb_caisse.blockSignals(True)
            self.cb_caisse.clear()
            self.cb_caisse.addItem("Toutes les Caisses", None)
            terminals = self.data_manager.pos_terminals.get_all_terminals(include_inactive=True) if hasattr(self.data_manager, 'pos_terminals') else []
            for t in terminals:
                display = f"{t.get('Terminal_Name')} ({t.get('Terminal_Code')})"
                self.cb_caisse.addItem(display, t.get('Terminal_Name'))
            self.cb_caisse.blockSignals(False)

    def load_sales_data(self):
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        client_id = self.cb_client.get_selected_client_id()

        self.raw_data = self.data_manager.sales.get_sales_operations_history(d_from, d_to, client_id)
        self.apply_filter_local()

    def apply_filter_local(self):
        txt = self.search_input.text().lower().strip()
        status = self.cb_status.currentData() if hasattr(self, "cb_status") else None
        payment = self.cb_payment.currentData() if hasattr(self, "cb_payment") else None
        caisse = self.cb_caisse.currentData() if hasattr(self, "cb_caisse") else None
        overdue_only = self.chk_overdue_only.isChecked() if hasattr(self, "chk_overdue_only") else False
        aging_bucket = self.cb_aging.currentData() if hasattr(self, "cb_aging") else "all"

        filtered = []
        for inv in self.raw_data:
            full_text = (
                f"{inv.get('Operation_ID','')} #{inv.get('Invoice_ID','')} "
                f"{inv.get('Invoice_No','')} {inv.get('Operation_Label','')} "
                f"{inv.get('Client_Name','')} {inv.get('Status','')} "
                f"{inv.get('Caisse_Label','')} {inv.get('Terminal_Name','')} "
                f"{inv.get('User_Name','')} {inv.get('Session_No','')} "
                f"{inv.get('Payment_Summary','')}"
            ).lower()
            if txt and txt not in full_text:
                continue
            if status and inv.get('Status') != status:
                continue
            if caisse:
                inv_caisse = str(inv.get('Caisse_Label') or inv.get('Terminal_Name') or '')
                if caisse.lower() not in inv_caisse.lower():
                    continue
            if payment and inv.get('Row_Type') == 'Sale':
                methods = str(inv.get('Payment_Summary') or inv.get('Payment_Method') or '')
                if payment not in methods:
                    continue

            # AR Aging / Overdue filtering
            if overdue_only:
                if inv.get('Row_Type') != 'Sale':
                    continue
                if inv.get('Status') == 'Cancelled':
                    continue
                total_ttc = float(inv.get('Total_Amount_TTC') or 0.0)
                paid_amount = float(inv.get('Paid_Amount') or 0.0)
                if total_ttc - paid_amount <= 0.01:
                    continue

                days = inv.get('Days_Overdue')
                if days is None and inv.get('Due_Date'):
                    try:
                        due_dt = datetime.strptime(str(inv.get('Due_Date'))[:10], "%Y-%m-%d").date()
                        days = (datetime.now().date() - due_dt).days
                    except Exception:
                        days = 0
                days = int(days or 0) if days is not None else 0
                if days < 0:
                    continue

                if (aging_bucket == "0-30" or aging_bucket == "1-30") and not (0 <= days <= 30):
                    continue
                elif aging_bucket == "31-60" and not (31 <= days <= 60):
                    continue
                elif aging_bucket == ">60" and not (days > 60):
                    continue

            filtered.append(inv)

        self.filtered_data = filtered
        self.update_summary_metrics()
        self.reset_and_reload()

    def _on_scroll(self, value):
        scroll_bar = self.table.verticalScrollBar()
        if scroll_bar.maximum() > 0 and value >= scroll_bar.maximum() - 20:
            self.load_next_batch()

    def reset_and_reload(self):
        self.current_offset = 0
        self.has_more_data = True
        self.table.setRowCount(0)
        self.load_next_batch()

    def load_data(self):
        """Compatibility entry point used by MainWindow and tabs."""
        self.load_sales_data()

    def load_next_batch(self):
        if self.is_loading or not self.has_more_data:
            return

        self.is_loading = True
        self.lbl_status.setText("⏳ Chargement...")

        try:
            batch = self.filtered_data[self.current_offset : self.current_offset + self.batch_size]
            if not batch:
                self.has_more_data = False
            else:
                self._append_rows_to_table(batch)
                self.current_offset += len(batch)
                if self.current_offset >= len(self.filtered_data):
                    self.has_more_data = False

            self.update_status_ui()
        except Exception as error:
            logging.error("Error fetching lazy sales batch: %s", error)
            self.lbl_status.setText("⚠️ Erreur lors du chargement")
        finally:
            self.is_loading = False

    def update_status_ui(self):
        total = len(self.filtered_data)
        self.lbl_status.setText(f"{self.table.rowCount()}/{total}")

    def update_summary_metrics(self):
        status_filter = self.cb_status.currentData() if hasattr(self, 'cb_status') else None
        sales_ops = [inv for inv in self.filtered_data if inv.get('Row_Type') == 'Sale']
        valid_sales = [inv for inv in sales_ops if inv.get('Status') != 'Cancelled'] if status_filter != 'Cancelled' else sales_ops

        sales_count = len(valid_sales)
        total_cost = sum(float(inv.get('Total_Cost') or 0.0) for inv in valid_sales)
        total_sales = sum(float(inv.get('Total_Amount_TTC') or 0.0) for inv in valid_sales)
        total_profit = sum(float(inv.get('Total_Profit') or 0.0) for inv in valid_sales)

        self.lbl_sales_count.setText(f"🧾 Ventes : {sales_count}")
        self.lbl_total_sales.setText(f"💰 Total Ventes : {format_money(total_sales)} DA")

        if self.can_view_profit:
            self.lbl_total_cost.setText(f"📦 Coût Achat : {format_money(total_cost)} DA")
            self.lbl_total_period_profit.setText(f"📈 Bénéfice : {format_money(total_profit)} DA")
        else:
            self.lbl_total_cost.setText("📦 Coût Achat : accès restreint")
            self.lbl_total_period_profit.setText("📈 Bénéfice : accès restreint")

    def _populate_table(self, data):
        """Compatibility wrapper for appending rows."""
        self._append_rows_to_table(data)

    def _append_rows_to_table(self, data):
        self.table.setSortingEnabled(False)
        start_row = self.table.rowCount()

        for i, inv in enumerate(data):
            r = start_row + i
            self.table.insertRow(r)

            def item(text, align=Qt.AlignCenter, color=None, font=None):
                val = str(text) if text is not None else "-"
                it = QTableWidgetItem(val)
                it.setTextAlignment(align)
                if color:
                    it.setForeground(QBrush(QColor(color)))
                if font:
                    it.setFont(font)
                return it

            row_type = inv.get('Row_Type', 'Sale')
            is_cash_row = row_type in {'Cash_Open', 'Cash_Close'}
            row_bg = QColor("#eef6ff") if row_type == 'Cash_Open' else QColor("#fff7e6") if row_type == 'Cash_Close' else None
            row_font = QFont("Segoe UI", 9, QFont.Bold) if is_cash_row else None

            # Store row data in first item
            invoice_label = inv.get('Invoice_No') or inv.get('Operation_ID') or f"#{inv.get('Invoice_ID')}"
            id_item = item(invoice_label)
            id_item.setData(Qt.UserRole, inv)
            self.table.setItem(r, 0, id_item)

            self.table.setItem(r, 1, item(str(inv.get('Event_Date') or inv.get('Invoice_Date') or "-")))
            self.table.setItem(r, 2, item(inv.get('Operation_Label') or "Vente", font=row_font))

            client_name = inv.get('Client_Name')
            if not client_name:
                client_name = "Vente comptoir"
            self.table.setItem(r, 3, item(client_name, Qt.AlignLeft | Qt.AlignVCenter, font=QFont("Segoe UI", 9, QFont.Bold)))

            status_item = item(inv['Status'])
            self.table.setItem(r, 4, status_item)

            # Retard (Jours)
            if row_type == 'Sale':
                due_date_val = inv.get('Due_Date')
                total_ttc = float(inv.get('Total_Amount_TTC') or 0.0)
                paid_amount = float(inv.get('Paid_Amount') or 0.0)
                is_settled = (total_ttc - paid_amount <= 0.01)

                days = inv.get('Days_Overdue')
                if days is None and due_date_val and str(due_date_val) != 'None':
                    try:
                        due_dt = datetime.strptime(str(due_date_val)[:10], "%Y-%m-%d").date()
                        days = (datetime.now().date() - due_dt).days
                    except Exception:
                        days = None
                days = int(days) if days is not None else None

                if inv.get('Status') == 'Cancelled':
                    retard_item = item("Annulée", color="#94a3b8")
                elif is_settled:
                    retard_item = item("Soldée", color="#059669", font=QFont("Segoe UI", 9, QFont.Bold))
                elif days is not None and days > 0:
                    retard_item = item(f"+{days} j", color="#b91c1c", font=QFont("Segoe UI", 9, QFont.Bold))
                    retard_item.setBackground(QBrush(QColor("#fee2e2")))
                elif days is not None and days <= 0:
                    retard_item = item(f"{abs(days)} j", color="#0284c7")
                else:
                    retard_item = item("-")
            else:
                retard_item = item("-")
            self.table.setItem(r, 5, retard_item)

            caisse_display = inv.get('Caisse_Label') or inv.get('Terminal_Name') or "-"
            caisse_item = item(caisse_display)
            if is_cash_row:
                caisse_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                caisse_item.setForeground(QBrush(QColor("#007572")))
            self.table.setItem(r, 6, caisse_item)

            self.table.setItem(r, 7, item(inv.get('User_Name') or "-"))
            payment_text = inv.get("Payment_Summary") or inv.get("Payment_Method") or "-"
            self.table.setItem(r, 8, item(payment_text))

            if row_type == "Cash_Open":
                amount_entered = inv.get("Opening_Amount")
                amt_item = item(f"Fond: {format_money(amount_entered)} DA" if amount_entered is not None else "-")
                amt_item.setForeground(QBrush(QColor("#007572")))
                amt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(r, 9, amt_item)
                self.table.setItem(r, 10, item("---"))
            elif row_type == "Cash_Close":
                amount_entered = inv.get("Counted_Cash")
                amt_item = item(f"Compté: {format_money(amount_entered)} DA" if amount_entered is not None else "-")
                amt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(r, 9, amt_item)

                diff = float(inv.get('Cash_Difference') or 0.0)
                diff_sign = "+" if diff > 0 else ""
                diff_color = "#27ae60" if abs(diff) < 0.01 else ("#2980b9" if diff > 0 else "#c0392b")
                diff_item = item(f"Écart: {diff_sign}{format_money(diff)} DA", color=diff_color, font=QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(r, 10, diff_item)
            else:
                amount_entered = inv.get("Paid_Amount")
                self.table.setItem(r, 9, item(format_money(amount_entered) if amount_entered is not None else "-"))
                self.table.setItem(r, 10, item(format_money(inv.get('Total_Amount_TTC', 0))))

            profit = float(inv.get('Total_Profit') or 0) if self.can_view_profit else 0
            profit_item = item(format_money(profit), Qt.AlignCenter, "#27ae60" if profit > 0 else "#c0392b", QFont("Segoe UI", 9, QFont.Bold)) if row_type == 'Sale' else item("---")
            self.table.setItem(r, 11, profit_item)

            # 12. Quick-Action Button (Encaisser)
            is_overdue = False
            if row_type == 'Sale':
                if days is not None and days >= 0 and not is_settled and inv.get('Status') != 'Cancelled':
                    is_overdue = True

                if inv.get('Status') == 'Cancelled':
                    self.table.setItem(r, 12, item("Annulée", color="#94a3b8"))
                elif is_settled:
                    self.table.setItem(r, 12, item("Soldée", color="#059669", font=QFont("Segoe UI", 9, QFont.Bold)))
                else:
                    btn_pay = QPushButton("💳 Encaisser")
                    btn_pay.setCursor(Qt.PointingHandCursor)
                    btn_pay.setToolTip("Encaisser le règlement de cette facture")
                    btn_pay.setStyleSheet("""
                        QPushButton {
                            background-color: #0f766e;
                            color: white;
                            font-weight: bold;
                            font-size: 11px;
                            border-radius: 4px;
                            padding: 3px 8px;
                            border: none;
                        }
                        QPushButton:hover { background-color: #115e59; }
                    """)
                    btn_pay.clicked.connect(lambda _, invoice=inv: self._open_payment_settlement(invoice))
                    btn_container = QWidget()
                    btn_container.setStyleSheet("background: transparent;")
                    btn_layout = QHBoxLayout(btn_container)
                    btn_layout.setContentsMargins(2, 2, 2, 2)
                    btn_layout.setAlignment(Qt.AlignCenter)
                    btn_layout.addWidget(btn_pay)
                    self.table.setCellWidget(r, 12, btn_container)
            else:
                self.table.setItem(r, 12, item("-"))

            # Highlight overdue rows with soft red visual cues
            if is_overdue:
                for col in range(12):
                    cell = self.table.item(r, col)
                    if cell and col != 5:
                        cell.setBackground(QBrush(QColor("#fef2f2")))
            elif row_bg:
                for col in range(self.table.columnCount()):
                    cell = self.table.item(r, col)
                    if cell:
                        cell.setBackground(QBrush(row_bg))
                        cell.setFont(row_font)

    def show_full_details(self):
        row = self.table.currentRow()
        if row < 0:
            return
        data = self.table.item(row, 0).data(Qt.UserRole)
        if not data:
            return

        row_type = data.get('Row_Type')
        if row_type == 'Sale':
            dlg = SaleDetailsDialog(self.data_manager, data, self)
            dlg.exec()
        elif row_type in ('Cash_Open', 'Cash_Close'):
            session_id = data.get('Cash_Session_ID')
            if session_id:
                from ui.widgets.sales.dialogs import CashSessionDetailsDialog
                dlg = CashSessionDetailsDialog(self.data_manager, session_id, parent=self)
                dlg.exec()

    def on_selection_changed(self):
        row = self.table.currentRow()
        data = self.table.item(row, 0).data(Qt.UserRole) if row >= 0 and self.table.item(row, 0) else None
        has_selection = bool(data and data.get('Row_Type') == 'Sale')
        self.btn_print_selected.setEnabled(has_selection)

        if hasattr(self, 'btn_settle_payment'):
            can_settle = False
            if has_selection and data.get('Status') != 'Cancelled':
                total_ttc = float(data.get('Total_Amount_TTC') or 0.0)
                paid_amount = float(data.get('Paid_Amount') or 0.0)
                can_settle = (total_ttc - paid_amount > 0.01)
            self.btn_settle_payment.setEnabled(can_settle)

    def export_filtered_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exporter l'historique", "historique_ventes.csv", "CSV (*.csv)")
        if not path:
            return
        headers = [
            "ID", "Date", "Operation", "Client", "Statut",
            "Retard (Jours)", "Caisse", "Utilisateur", "Paiement", "Paye", "Total TTC", "Cout Achat", "Profit"
        ]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                for inv in self.filtered_data:
                    writer.writerow([
                        inv.get("Invoice_No") or inv.get("Operation_ID") or inv.get("Invoice_ID"),
                        inv.get("Event_Date") or inv.get("Invoice_Date"),
                        inv.get("Operation_Label"),
                        inv.get("Client_Name") or "-",
                        inv.get("Status") or "-",
                        inv.get("Days_Overdue") if inv.get("Days_Overdue") is not None else "-",
                        inv.get("Caisse_Label") or inv.get("Terminal_Name") or "-",
                        inv.get("User_Name") or "-",
                        inv.get("Payment_Summary") or inv.get("Payment_Method") or "-",
                        inv.get("Paid_Amount") if inv.get("Row_Type") == "Sale" else inv.get("Amount_Entered"),
                        inv.get("Total_Amount_TTC") or 0,
                        (inv.get("Total_Cost") or 0) if self.can_view_profit else "-",
                        (inv.get("Total_Profit") or 0) if self.can_view_profit else "-",
                    ])
            QMessageBox.information(self, "Export", "Historique exporte avec succes.")
        except OSError as exc:
            QMessageBox.warning(self, "Export", f"Echec de l'export: {exc}")

    def print_selected_invoice(self):
        row = self.table.currentRow()
        if row < 0:
            return
        data = self.table.item(row, 0).data(Qt.UserRole)
        if data and data.get('Row_Type') == 'Sale':
            export_invoice_to_pdf(self.data_manager, data, self)
