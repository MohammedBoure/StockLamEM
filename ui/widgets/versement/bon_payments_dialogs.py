# -*- coding: utf-8 -*-
"""
Clean modal dialogs for adding and editing payments on a Bon
(shared across Versement and Paiement Livraison workspaces).
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon

logger = logging.getLogger("StockLam.UI.BonPaymentsDialogs")

PAYMENT_METHODS = [
    ("Cash", "Espèces", "pay_cash"),
    ("BaridiMob", "BaridiMob", "pay_baridimob"),
    ("TPE", "TPE", "pay_tpe"),
    ("CCP", "CCP", "pay_ccp"),
]


def _resolve_bonds_manager(data_manager: Any):
    if data_manager is None:
        return None
    mgr = getattr(data_manager, "bonds", None)
    if mgr is not None:
        return mgr
    db = getattr(data_manager, "db", None)
    if db is not None:
        try:
            from database.bond_lifecycle_manager import BondLifecycleManager

            return BondLifecycleManager(db)
        except Exception:
            return None
    return None


class BonPaymentAddDialog(QDialog):
    """Focused modal dialog for adding a new payment (Versement) to a Bon."""

    def __init__(
        self,
        data_manager: Any,
        bon_data: Dict[str, Any],
        current_user: Optional[Dict[str, Any]] = None,
        dialog_title: str = "Ajouter un Versement",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self._bonds_mgr = _resolve_bonds_manager(data_manager)
        self.bon_data = dict(bon_data or {})
        self.current_user = current_user or {}
        self.result_data: Optional[Dict[str, Any]] = None

        self.setWindowTitle(dialog_title)
        self.setModal(True)
        self.resize(480, 410)
        self._init_ui()
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            geo = parent.frameGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    def _init_ui(self) -> None:
        self.setObjectName("BonPaymentAddDialog")
        self.setStyleSheet(
            """
            QDialog#BonPaymentAddDialog {
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #334155;
            }
            QFrame#BonSummaryStrip {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QDoubleSpinBox, QLineEdit, QDateEdit {
                background-color: #FFFFFF;
                border: 1.5px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                color: #0F172A;
                font-size: 13px;
                font-weight: 600;
            }
            QDoubleSpinBox:focus, QLineEdit:focus, QDateEdit:focus {
                border-color: #0E7471;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("payment", 24).pixmap(24, 24))
        hdr.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        ord_num = str(self.bon_data.get("Order_Number") or f"Bon #{self.bon_data.get('Order_ID', '')}")
        client_name = str(self.bon_data.get("Client_Name") or "Client")
        self.lbl_bon_header = QLabel(ord_num)
        self.lbl_bon_header.setStyleSheet("font-size: 15px; font-weight: 700; color: #0F172A;")
        self.lbl_client_header = QLabel(client_name)
        self.lbl_client_header.setStyleSheet("font-size: 12px; color: #64748B;")
        title_col.addWidget(self.lbl_bon_header)
        title_col.addWidget(self.lbl_client_header)
        hdr.addLayout(title_col, 1)
        root.addLayout(hdr)

        # Summary strip
        total_ttc = float(self.bon_data.get("Total_Amount_TTC") or 0.0)
        total_paid = float(self.bon_data.get("Total_Paid") or 0.0)
        remaining = max(0.0, float(self.bon_data.get("Remaining_Amount") or max(0.0, total_ttc - total_paid)))
        self._remaining = remaining

        strip = QFrame()
        strip.setObjectName("BonSummaryStrip")
        strip_lay = QHBoxLayout(strip)
        strip_lay.setContentsMargins(12, 10, 12, 10)
        strip_lay.setSpacing(12)

        for title_txt, val_txt, color_hex in (
            ("Total Bon", format_money(total_ttc), "#0F172A"),
            ("Déjà Versé", format_money(total_paid), "#0E7471"),
            ("Reste à Payer", format_money(remaining), "#D97706" if remaining > 0.01 else "#16A34A"),
        ):
            col = QVBoxLayout()
            col.setSpacing(2)
            t = QLabel(title_txt)
            t.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748B;")
            v = QLabel(val_txt)
            v.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {color_hex};")
            col.addWidget(t)
            col.addWidget(v)
            strip_lay.addLayout(col, 1)

        root.addWidget(strip)

        # Amount row
        amt_label = QLabel("Montant du versement (DA)")
        amt_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        root.addWidget(amt_label)

        amt_row = QHBoxLayout()
        amt_row.setSpacing(8)
        self.txt_amount = QDoubleSpinBox()
        self.txt_amount.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.txt_amount.setRange(0.0, 999999999.99)
        self.txt_amount.setDecimals(2)
        self.txt_amount.setSuffix(" DA")
        self.txt_amount.setFixedHeight(38)
        self.txt_amount.setValue(remaining if remaining > 0 else 0.0)
        self.txt_amount.valueChanged.connect(self._validate_live)
        amt_row.addWidget(self.txt_amount, 1)

        self.btn_fill_remaining = QPushButton("Tout Solder")
        self.btn_fill_remaining.setFixedHeight(38)
        self.btn_fill_remaining.setCursor(Qt.PointingHandCursor)
        self.btn_fill_remaining.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF;
                border: 1.5px solid #0E7471;
                border-radius: 6px;
                color: #0E7471;
                font-size: 12px;
                font-weight: 700;
                padding: 0 12px;
            }
            QPushButton:hover { background-color: #E6F4F1; }
            """
        )
        self.btn_fill_remaining.clicked.connect(lambda: self.txt_amount.setValue(self._remaining))
        amt_row.addWidget(self.btn_fill_remaining)
        root.addLayout(amt_row)

        # Payment method visual strip
        method_lbl = QLabel("Mode de paiement")
        method_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        root.addWidget(method_lbl)

        method_row = QHBoxLayout()
        method_row.setSpacing(8)
        self.method_group = QButtonGroup(self)
        self.method_group.setExclusive(True)
        self.method_buttons: Dict[str, QPushButton] = {}
        for idx, (code, label, icon_name) in enumerate(PAYMENT_METHODS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(get_duotone_icon(icon_name, 16))
            btn.setIconSize(QSize(16, 16))
            btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    border-radius: 6px;
                    color: #334155;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 8px;
                }
                QPushButton:checked {
                    background-color: #E6F4F1;
                    border: 1.5px solid #0E7471;
                    color: #0E7471;
                    font-weight: 700;
                }
                QPushButton:hover:!checked { background-color: #F8FAFC; }
                """
            )
            self.method_group.addButton(btn)
            self.method_buttons[code] = btn
            method_row.addWidget(btn, 1)
        root.addLayout(method_row)

        # Date & Notes row
        dn_row = QHBoxLayout()
        dn_row.setSpacing(10)

        date_col = QVBoxLayout()
        date_col.setSpacing(4)
        dl = QLabel("Date")
        dl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setFixedHeight(36)
        date_col.addWidget(dl)
        date_col.addWidget(self.date_edit)
        dn_row.addLayout(date_col, 1)

        notes_col = QVBoxLayout()
        notes_col.setSpacing(4)
        nl = QLabel("Notes / Référence")
        nl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        self.txt_notes = QLineEdit()
        self.txt_notes.setFixedHeight(36)
        self.txt_notes.setPlaceholderText("Observation optionnelle...")
        notes_col.addWidget(nl)
        notes_col.addWidget(self.txt_notes)
        dn_row.addLayout(notes_col, 2)
        root.addLayout(dn_row)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("font-size: 12px; font-weight: 600; color: #DC2626;")
        self.lbl_error.setVisible(False)
        root.addWidget(self.lbl_error)

        # Footer buttons
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 0 18px;
            }
            QPushButton:hover { background-color: #F8FAFC; }
            """
        )
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Enregistrer Versement")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setIcon(get_duotone_icon("payment_white", 16))
        self.btn_save.setIconSize(QSize(16, 16))
        self.btn_save.setStyleSheet(
            """
            QPushButton {
                background-color: #0E7471;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 700;
                padding: 0 18px;
            }
            QPushButton:hover { background-color: #0A5C59; }
            QPushButton:disabled { background-color: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; }
            """
        )
        self.btn_save.clicked.connect(self._on_save)
        footer.addWidget(self.btn_save)
        root.addLayout(footer)

        self._validate_live()

    def _selected_payment_method(self) -> str:
        for code, btn in self.method_buttons.items():
            if btn.isChecked():
                return code
        return "Cash"

    def _validate_live(self) -> None:
        val = float(self.txt_amount.value())
        if val <= 0.0:
            self.lbl_error.setText("Le montant doit être supérieur à 0 DA.")
            self.lbl_error.setVisible(True)
            self.btn_save.setEnabled(False)
            self.btn_save.setToolTip("Saisissez un montant valide supérieur à 0,00 DA")
            return
        if self._remaining > 0.0 and val > self._remaining + 0.01:
            self.lbl_error.setText(f"Le montant dépasse le reste à payer ({format_money(self._remaining)}).")
            self.lbl_error.setVisible(True)
            self.btn_save.setEnabled(False)
            self.btn_save.setToolTip(f"Le montant saisi dépasse le reste à payer ({format_money(self._remaining)})")
            return
        if self._remaining <= 0.01:
            self.lbl_error.setText("Ce bon est déjà intégralement soldé.")
            self.lbl_error.setVisible(True)
            self.btn_save.setEnabled(False)
            self.btn_save.setToolTip("Ce bon est déjà intégralement soldé")
            return
        self.lbl_error.setVisible(False)
        self.btn_save.setEnabled(True)
        self.btn_save.setToolTip("Enregistrer cette tranche de paiement")

    def _on_save(self) -> None:
        if self._bonds_mgr is None:
            QMessageBox.critical(self, "Erreur", "Gestionnaire de bons indisponible.")
            return
        order_id = int(self.bon_data.get("Order_ID") or 0)
        amount = Decimal(str(self.txt_amount.value())).quantize(Decimal("0.01"))
        method = self._selected_payment_method()
        pay_date = self.date_edit.date().toString("yyyy-MM-dd")
        notes = self.txt_notes.text().strip()
        user_id = int(self.current_user.get("User_ID") or 1) if isinstance(self.current_user, dict) else 1

        try:
            self.result_data = self._bonds_mgr.add_payment_to_bon(
                order_id=order_id,
                amount=amount,
                payment_method=method,
                payment_date=pay_date,
                notes=notes,
                user_id=user_id,
            )
            self.accept()
        except Exception as err:
            QMessageBox.warning(self, "Validation Versement", str(err))


class BonPaymentsManageDialog(QDialog):
    """
    Modal dialog displaying all payments for a single Bon with direct inline editing,
    deletion of installment payments, and one-click addition of a new payment.
    """

    def __init__(
        self,
        data_manager: Any,
        order_id: int,
        current_user: Optional[Dict[str, Any]] = None,
        dialog_title: str = "Gérer les Versements du Bon",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self._bonds_mgr = _resolve_bonds_manager(data_manager)
        self.order_id = int(order_id)
        self.current_user = current_user or {}
        self.has_changes = False
        self._bon_summary: Dict[str, Any] = {}
        self._payments: List[Dict[str, Any]] = []
        self._editing_entry: Optional[Dict[str, Any]] = None

        self.setWindowTitle(dialog_title)
        self.setModal(True)
        self.resize(760, 520)
        self._init_ui()
        self.refresh_data()
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            geo = parent.frameGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    def _init_ui(self) -> None:
        self.setObjectName("BonPaymentsManageDialog")
        self.setStyleSheet(
            """
            QDialog#BonPaymentsManageDialog {
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #334155;
            }
            QFrame#ManageSummaryCard, QFrame#InlineEditCard {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QDoubleSpinBox, QComboBox, QDateEdit, QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 8px;
                color: #0F172A;
                font-size: 12px;
                font-weight: 600;
            }
            QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus, QLineEdit:focus {
                border: 1.5px solid #0E7471;
            }
            QTableWidget#BonPaymentsTable {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                gridline-color: #F1F5F9;
                alternate-background-color: #F8FAFC;
                selection-background-color: #E6F4F1;
                selection-color: #0F172A;
            }
            QTableWidget#BonPaymentsTable QHeaderView::section {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 8px;
                border: none;
                border-bottom: 2px solid #0E7471;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header + Direct Add Button
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("kpi_wallet", 24).pixmap(24, 24))
        top_row.addWidget(icon_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.lbl_title = QLabel("Bon")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet("font-size: 12px; color: #64748B;")
        info_col.addWidget(self.lbl_title)
        info_col.addWidget(self.lbl_sub)
        top_row.addLayout(info_col, 1)

        self.btn_add_payment = QPushButton("Ajouter Versement")
        self.btn_add_payment.setFixedHeight(36)
        self.btn_add_payment.setCursor(Qt.PointingHandCursor)
        self.btn_add_payment.setIcon(get_duotone_icon("payment_white", 16))
        self.btn_add_payment.setIconSize(QSize(16, 16))
        self.btn_add_payment.setStyleSheet(
            """
            QPushButton {
                background-color: #0E7471;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover { background-color: #0A5C59; }
            QPushButton:disabled { background-color: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; }
            """
        )
        self.btn_add_payment.clicked.connect(self._open_add_dialog)
        top_row.addWidget(self.btn_add_payment)
        root.addLayout(top_row)

        # Summary card
        summary_card = QFrame()
        summary_card.setObjectName("ManageSummaryCard")
        s_lay = QHBoxLayout(summary_card)
        s_lay.setContentsMargins(14, 10, 14, 10)
        s_lay.setSpacing(16)

        self.lbl_sum_total = QLabel("Total : 0.00 DA")
        self.lbl_sum_total.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A;")
        self.lbl_sum_paid = QLabel("Payé : 0.00 DA")
        self.lbl_sum_paid.setStyleSheet("font-size: 13px; font-weight: 700; color: #0E7471;")
        self.lbl_sum_rem = QLabel("Reste : 0.00 DA")
        self.lbl_sum_rem.setStyleSheet("font-size: 13px; font-weight: 700; color: #D97706;")

        s_lay.addWidget(self.lbl_sum_total)
        s_lay.addWidget(self.lbl_sum_paid)
        s_lay.addWidget(self.lbl_sum_rem)
        s_lay.addStretch()
        root.addWidget(summary_card)

        # Payments Table
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("BonPaymentsTable")
        self.table.setHorizontalHeaderLabels(["Date", "Source", "Mode", "Montant", "Notes", "Actions"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 165)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        root.addWidget(self.table, 1)

        # Inline Quick Edit Card (hidden until user clicks Modifier on a row)
        self.edit_card = QFrame()
        self.edit_card.setObjectName("InlineEditCard")
        self.edit_card.setVisible(False)
        e_lay = QVBoxLayout(self.edit_card)
        e_lay.setContentsMargins(12, 10, 12, 10)
        e_lay.setSpacing(8)

        self.lbl_edit_title = QLabel("Modifier le paiement sélectionné")
        self.lbl_edit_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #0E7471;")
        e_lay.addWidget(self.lbl_edit_title)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(8)

        self.edit_amount = QDoubleSpinBox()
        self.edit_amount.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.edit_amount.setRange(0.01, 999999999.99)
        self.edit_amount.setDecimals(2)
        self.edit_amount.setSuffix(" DA")
        self.edit_amount.setFixedHeight(36)
        self.edit_amount.setMinimumWidth(140)

        self.edit_method = QComboBox()
        self.edit_method.addItems(["Cash", "BaridiMob", "TPE", "CCP"])
        self.edit_method.setFixedHeight(36)
        self.edit_method.setMinimumWidth(115)

        self.edit_date = QDateEdit()
        self.edit_date.setCalendarPopup(True)
        self.edit_date.setDisplayFormat("yyyy-MM-dd")
        self.edit_date.setFixedHeight(36)
        self.edit_date.setMinimumWidth(120)

        self.edit_notes = QLineEdit()
        self.edit_notes.setFixedHeight(36)
        self.edit_notes.setPlaceholderText("Notes...")

        self.btn_save_edit = QPushButton("Enregistrer")
        self.btn_save_edit.setFixedHeight(36)
        self.btn_save_edit.setCursor(Qt.PointingHandCursor)
        self.btn_save_edit.setStyleSheet(
            """
            QPushButton {
                background-color: #0E7471;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover { background-color: #0A5C59; }
            """
        )
        self.btn_save_edit.clicked.connect(self._save_inline_edit)

        self.btn_cancel_edit = QPushButton("Annuler")
        self.btn_cancel_edit.setFixedHeight(36)
        self.btn_cancel_edit.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_edit.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton:hover { background-color: #F8FAFC; }
            """
        )
        self.btn_cancel_edit.clicked.connect(self._hide_inline_edit)

        fields_row.addWidget(self.edit_amount)
        fields_row.addWidget(self.edit_method)
        fields_row.addWidget(self.edit_date)
        fields_row.addWidget(self.edit_notes, 1)
        fields_row.addWidget(self.btn_save_edit)
        fields_row.addWidget(self.btn_cancel_edit)
        e_lay.addLayout(fields_row)
        root.addWidget(self.edit_card)

        # Footer
        footer = QHBoxLayout()
        self.lbl_count = QLabel("0 versement(s)")
        self.lbl_count.setStyleSheet("font-size: 12px; color: #64748B;")
        footer.addWidget(self.lbl_count)
        footer.addStretch()

        self.btn_close = QPushButton("Fermer")
        self.btn_close.setFixedHeight(36)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 0 18px;
            }
            QPushButton:hover { background-color: #F8FAFC; }
            """
        )
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)
        root.addLayout(footer)

    def refresh_data(self) -> None:
        if self._bonds_mgr is None:
            return
        data = self._bonds_mgr.get_bon_payments(self.order_id)
        if not isinstance(data, dict):
            return

        self._bon_summary = dict(data.get("bon") or {})
        self._payments = list(data.get("payments") or [])

        ord_num = str(self._bon_summary.get("Order_Number") or f"Bon #{self.order_id}")
        client_name = str(self._bon_summary.get("Client_Name") or "Client")
        inv_no = str(self._bon_summary.get("Invoice_No") or "Non facturé")
        self.lbl_title.setText(f"{ord_num} — {client_name}")
        self.lbl_sub.setText(f"Facture : {inv_no}")

        total_ttc = float(self._bon_summary.get("Total_Amount_TTC") or 0.0)
        total_paid = float(self._bon_summary.get("Total_Paid") or 0.0)
        remaining = float(self._bon_summary.get("Remaining_Amount") or 0.0)

        self.lbl_sum_total.setText(f"Total : {format_money(total_ttc)}")
        self.lbl_sum_paid.setText(f"Payé : {format_money(total_paid)}")
        rem_color = "#D97706" if remaining > 0.01 else "#16A34A"
        self.lbl_sum_rem.setText(f"Reste : {format_money(remaining)}")
        self.lbl_sum_rem.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {rem_color};")

        self.btn_add_payment.setEnabled(remaining > 0.01)
        self.btn_add_payment.setToolTip(
            "Ajouter une nouvelle tranche de paiement"
            if remaining > 0.01
            else "Ce bon est déjà soldé (aucun reste à payer)"
        )
        self.lbl_count.setText(f"{len(self._payments)} paiement(s) enregistré(s)")

        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for row_idx, entry in enumerate(self._payments):
            self.table.insertRow(row_idx)
            self.table.setRowHeight(row_idx, 46)

            src_map = {
                "INVOICE_INITIAL": "Initial Caisse",
                "INVOICE_WALLET": "Portefeuille",
                "CLIENT_PAYMENT": "Versement",
            }
            etype = str(entry.get("entry_type") or "")

            it_date = QTableWidgetItem(str(entry.get("payment_date") or ""))
            it_src = QTableWidgetItem(src_map.get(etype, etype))
            it_mode = QTableWidgetItem(str(entry.get("payment_method") or "Cash"))

            it_amt = QTableWidgetItem(format_money(float(entry.get("amount") or 0.0)))
            it_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            f_bold = QFont()
            f_bold.setBold(True)
            it_amt.setFont(f_bold)
            it_amt.setForeground(QColor("#0E7471"))

            it_notes = QTableWidgetItem(str(entry.get("notes") or ""))

            self.table.setItem(row_idx, 0, it_date)
            self.table.setItem(row_idx, 1, it_src)
            self.table.setItem(row_idx, 2, it_mode)
            self.table.setItem(row_idx, 3, it_amt)
            self.table.setItem(row_idx, 4, it_notes)

            action_cell = QWidget()
            action_cell.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(action_cell)
            a_lay.setContentsMargins(6, 8, 6, 8)
            a_lay.setSpacing(6)

            if entry.get("editable"):
                btn_edit = QPushButton("Modifier")
                btn_edit.setFixedHeight(28)
                btn_edit.setCursor(Qt.PointingHandCursor)
                btn_edit.setIcon(get_duotone_icon("edit", 14))
                btn_edit.setIconSize(QSize(14, 14))
                btn_edit.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #FFFFFF;
                        border: 1px solid #CBD5E1;
                        border-radius: 5px;
                        color: #0F172A;
                        font-size: 11px;
                        font-weight: 600;
                        padding: 2px 8px;
                    }
                    QPushButton:hover {
                        border-color: #0E7471;
                        color: #0E7471;
                        background-color: #E6F4F1;
                    }
                    """
                )
                btn_edit.clicked.connect(lambda _=False, ent=entry: self._start_inline_edit(ent))
                a_lay.addWidget(btn_edit)

            if entry.get("deletable") and entry.get("payment_id"):
                btn_del = QPushButton()
                btn_del.setFixedSize(28, 28)
                btn_del.setCursor(Qt.PointingHandCursor)
                btn_del.setToolTip("Supprimer ce paiement")
                btn_del.setIcon(get_duotone_icon("trash", 14))
                btn_del.setIconSize(QSize(14, 14))
                btn_del.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #FFFFFF;
                        border: 1px solid #FECACA;
                        border-radius: 5px;
                    }
                    QPushButton:hover { background-color: #FEE2E2; }
                    """
                )
                btn_del.clicked.connect(lambda _=False, pid=int(entry["payment_id"]): self._delete_payment(pid))
                a_lay.addWidget(btn_del)

            a_lay.addStretch()
            self.table.setCellWidget(row_idx, 5, action_cell)

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._payments):
            entry = self._payments[row]
            if entry.get("editable"):
                self._start_inline_edit(entry)

    def _start_inline_edit(self, entry: Dict[str, Any]) -> None:
        self._editing_entry = dict(entry)
        self.edit_amount.setValue(float(entry.get("amount") or 0.0))

        method = str(entry.get("payment_method") or "Cash")
        idx = self.edit_method.findText(method)
        self.edit_method.setCurrentIndex(idx if idx >= 0 else 0)

        date_str = str(entry.get("payment_date") or "")[:10]
        qd = QDate.fromString(date_str, "yyyy-MM-dd")
        self.edit_date.setDate(qd if qd.isValid() else QDate.currentDate())
        self.edit_notes.setText(str(entry.get("notes") or ""))
        self.edit_card.setVisible(True)
        self.edit_amount.setFocus()

    def _hide_inline_edit(self) -> None:
        self._editing_entry = None
        self.edit_card.setVisible(False)

    def _save_inline_edit(self) -> None:
        if not self._editing_entry or self._bonds_mgr is None:
            return
        new_amt = Decimal(str(self.edit_amount.value())).quantize(Decimal("0.01"))
        new_method = self.edit_method.currentText()
        new_date = self.edit_date.date().toString("yyyy-MM-dd")
        new_notes = self.edit_notes.text().strip()

        try:
            self._bonds_mgr.update_bon_payment(
                order_id=self.order_id,
                entry_type=str(self._editing_entry.get("entry_type") or "CLIENT_PAYMENT"),
                payment_id=self._editing_entry.get("payment_id"),
                new_amount=new_amt,
                payment_method=new_method,
                payment_date=new_date,
                notes=new_notes,
            )
            self.has_changes = True
            self._hide_inline_edit()
            self.refresh_data()
        except Exception as err:
            QMessageBox.warning(self, "Modification Paiement", str(err))

    def _delete_payment(self, payment_id: int) -> None:
        if self._bonds_mgr is None:
            return
        confirm = QMessageBox.question(
            self,
            "Confirmation",
            "Voulez-vous supprimer ce paiement ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self._bonds_mgr.delete_bon_payment(self.order_id, int(payment_id))
            self.has_changes = True
            self._hide_inline_edit()
            self.refresh_data()
        except Exception as err:
            QMessageBox.warning(self, "Suppression Paiement", str(err))

    def _open_add_dialog(self) -> None:
        dlg = BonPaymentAddDialog(
            data_manager=self.data_manager,
            bon_data=self._bon_summary,
            current_user=self.current_user,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            self.has_changes = True
            self._hide_inline_edit()
            self.refresh_data()
