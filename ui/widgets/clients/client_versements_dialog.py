# -*- coding: utf-8 -*-
"""
Minimalist, container-free dialog displaying a client's past Versements and current wallet balance.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money

logger = logging.getLogger(__name__)


TX_TYPE_LABELS = {
    "REAL_CASH_VERSEMENT": "Versement Espèces",
    "RETURN_VIRTUAL_CREDIT": "Avoir Bon de Retour",
    "SAV_IRREPARABLE_COMPENSATION": "Compensation SAV",
    "SALES_PURCHASE_DEBIT": "Déduction sur Achat",
    "ADMIN_ADJUSTMENT": "Ajustement",
    "CASH_DISBURSEMENT_REFUND": "Remboursement",
}


class ClientVersementsDialog(QDialog):
    """Sleek, clutter-free dialog showing past Versement operations and current client balance."""

    def __init__(
        self,
        data_manager: Any,
        client_id: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.default_client_id = client_id
        self._bonds_mgr = getattr(data_manager, "bonds", None)
        if self._bonds_mgr is None and hasattr(data_manager, "db") and data_manager.db:
            try:
                from database.bond_lifecycle_manager import BondLifecycleManager

                self._bonds_mgr = BondLifecycleManager(data_manager.db)
            except Exception:
                self._bonds_mgr = None

        self.setWindowTitle("Versements & Solde Client")
        self.resize(680, 440)
        self._init_ui()
        self._load_clients()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; color: #1E293B; }
            QLabel { border: none; background: transparent; color: #1E293B; }
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #0F172A;
            }
            QComboBox:focus { border: 1.5px solid #007572; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        # Single clean top row: Client Selector + Inline Balance Metrics (no extra containers)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.cbo_client = QComboBox()
        self.cbo_client.setEditable(True)
        self.cbo_client.setFixedHeight(36)
        self.cbo_client.setMinimumWidth(230)
        if self.cbo_client.lineEdit():
            self.cbo_client.lineEdit().setPlaceholderText("Sélectionner un client...")
        self.cbo_client.currentIndexChanged.connect(self.refresh_wallet_data)
        top_row.addWidget(self.cbo_client, 1)

        self.lbl_balance_summary = QLabel("Solde : <b>0.00 DA</b>")
        self.lbl_balance_summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_balance_summary.setStyleSheet("font-size: 13px; color: #334155;")
        top_row.addWidget(self.lbl_balance_summary)

        layout.addLayout(top_row)

        # Clean single Table for Versements history
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date", "Opération", "Montant", "Solde Après"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 5px;
                gridline-color: #F1F5F9;
                selection-background-color: #E6F4F1;
                selection-color: #0F172A;
                alternate-background-color: #F8FAFC;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 700;
                font-size: 12px;
                padding: 7px 10px;
                border: none;
                border-bottom: 2px solid #007572;
            }
        """)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        # Clean minimal footer
        footer = QHBoxLayout()
        self.lbl_count = QLabel("0 opération(s)")
        self.lbl_count.setStyleSheet("font-size: 11px; color: #64748B;")
        footer.addWidget(self.lbl_count)
        footer.addStretch()

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(36)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                padding: 0 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover { background-color: #005A57; }
        """)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def _load_clients(self) -> None:
        self.cbo_client.blockSignals(True)
        self.cbo_client.clear()

        clients: List[Dict[str, Any]] = []
        client_mgr = getattr(self.data_manager, "clients", None)
        if client_mgr and hasattr(client_mgr, "get_all_clients"):
            try:
                clients = client_mgr.get_all_clients() or []
            except Exception as err:
                logger.debug(f"Could not load clients in ClientVersementsDialog: {err}")

        sel_idx = 0
        for idx, c in enumerate(clients):
            cid = int(c.get("Client_ID") or 0)
            cname = str(c.get("Client_Name") or f"Client #{cid}").strip()
            phone = str(c.get("Phone") or "").strip()
            label = f"{cname} — {phone}" if phone else cname
            self.cbo_client.addItem(label, cid)
            if self.default_client_id is not None and cid == int(self.default_client_id):
                sel_idx = idx

        completer = QCompleter(self.cbo_client.model(), self.cbo_client)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cbo_client.setCompleter(completer)

        if self.cbo_client.count() > 0:
            self.cbo_client.setCurrentIndex(sel_idx)
        self.cbo_client.blockSignals(False)
        self.refresh_wallet_data()

    def refresh_wallet_data(self) -> None:
        cid = self.cbo_client.currentData()
        if not cid or not self._bonds_mgr:
            self.lbl_balance_summary.setText("Solde : <b>0.00 DA</b>")
            self.table.setRowCount(0)
            self.lbl_count.setText("0 opération(s)")
            return

        wallet = self._bonds_mgr.get_client_wallet(int(cid)) or {}
        txs = self._bonds_mgr.get_client_wallet_transactions(int(cid), limit=100) or []

        cur_bal = float(wallet.get("current_balance") or 0.0)
        real_bal = float(wallet.get("real_deposit_balance") or 0.0)
        virt_bal = float(wallet.get("virtual_credit_balance") or 0.0)

        self.lbl_balance_summary.setText(
            f"Solde Disponible : <b style='color:#007572; font-size:14px;'>{format_money(cur_bal)} DA</b>"
            f"  <span style='color:#94A3B8;'>•</span>  "
            f"<span style='font-size:12px; color:#475569;'>Espèces : <b>{format_money(real_bal)} DA</b>  |  "
            f"Avoir : <b>{format_money(virt_bal)} DA</b></span>"
        )

        self.table.setRowCount(0)
        for row, tx in enumerate(txs):
            self.table.insertRow(row)
            dt_str = str(tx.get("Created_At") or "")[:16]
            self.table.setItem(row, 0, QTableWidgetItem(dt_str))

            raw_type = str(tx.get("Transaction_Type") or "")
            label = TX_TYPE_LABELS.get(raw_type, raw_type)
            notes = str(tx.get("Transaction_Notes") or "").strip()
            op_txt = f"{label} — {notes}" if notes and notes.lower() != label.lower() else label
            self.table.setItem(row, 1, QTableWidgetItem(op_txt))

            amt = float(tx.get("Amount") or 0.0)
            is_debit = raw_type in ("SALES_PURCHASE_DEBIT", "CASH_DISBURSEMENT_REFUND")
            sign = "-" if is_debit else "+"
            it_amt = QTableWidgetItem(f"{sign} {format_money(amt)} DA")
            it_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_amt.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_amt.setForeground(QColor("#DC2626" if is_debit else "#16A34A"))
            self.table.setItem(row, 2, it_amt)

            bal_after = float(tx.get("Balance_After") or 0.0)
            it_after = QTableWidgetItem(f"{format_money(bal_after)} DA")
            it_after.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_after.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 3, it_after)

        self.lbl_count.setText(f"{len(txs)} opération(s)")
