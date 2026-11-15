# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/caisse_versement_flow_dialogs.py
===========================================================
Sequential dialogs for applying a client's Versement balance during Caisse checkout:
1. VersementTypeChoiceDialog: Allows choosing between Versement Réel and Versement Virtuel.
2. VersementAmountApplyDialog: Lets the cashier enter the exact deduction amount while
   prominently displaying the client's remaining balance (الباقي).
"""

from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon
from ui.widgets.appliance_desks._theme import (
    BRAND_TEAL,
    BRAND_TEAL_BORDER,
    BRAND_TEAL_TINT,
    CARD_BG,
    INPUT_QSS,
    PRIMARY_CTA_QSS,
    SLATE_OUTLINE_QSS,
    STATUS_DANGER,
    STATUS_INFO,
    STATUS_INFO_BG,
    STATUS_INFO_BORDER,
    STATUS_SUCCESS,
    SUBTLE_BG,
    TEXT_BODY,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def _center_dialog_on_screen(dlg: QDialog) -> None:
    screen = dlg.screen() or QGuiApplication.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        dlg.adjustSize()
        dlg.move(geo.center() - dlg.rect().center())


def _parse_decimal_input(text: str) -> float:
    raw = (text or "").strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


class VersementTypeChoiceDialog(QDialog):
    """First dialog: choose between Versement Réel or Versement Virtuel."""

    def __init__(
        self,
        client_name: str,
        real_balance: float,
        virtual_balance: float,
        parent=None,
    ):
        super().__init__(parent)
        self.client_name = str(client_name or "").strip() or "Client"
        self.real_balance = max(0.0, float(real_balance or 0.0))
        self.virtual_balance = max(0.0, float(virtual_balance or 0.0))
        self.selected_type: Optional[str] = None

        self.setWindowTitle("Utiliser Versement — Type de Solde")
        self.setFixedWidth(460)
        self.setModal(True)
        self._init_ui()
        _center_dialog_on_screen(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _center_dialog_on_screen(self)

    def _init_ui(self) -> None:
        self.setObjectName("VersementTypeChoiceDialog")
        self.setStyleSheet(f"""
            QDialog#VersementTypeChoiceDialog {{
                background-color: {CARD_BG};
            }}
            QDialog#VersementTypeChoiceDialog QLabel {{
                border: none;
                background: transparent;
                color: {TEXT_PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        hdr = QLabel("Choisir le type de Versement")
        hdr.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {TEXT_PRIMARY};")
        layout.addWidget(hdr)

        sub = QLabel(f"Client : <b>{self.client_name}</b> — Sélectionnez le solde à utiliser :")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-size: 12.5px; color: {TEXT_BODY};")
        layout.addWidget(sub)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.btn_real = QPushButton(f"Versement Réel\n{format_money(self.real_balance)} DA")
        self.btn_real.setObjectName("BtnChooseVersementReal")
        self.btn_real.setIcon(get_duotone_icon("pay_cash", 24))
        self.btn_real.setIconSize(QSize(24, 24))
        self.btn_real.setCursor(Qt.PointingHandCursor)
        self.btn_real.setMinimumHeight(86)
        self.btn_real.setStyleSheet(f"""
            QPushButton {{
                background-color: {BRAND_TEAL_TINT};
                color: {BRAND_TEAL};
                border: 1.5px solid {BRAND_TEAL_BORDER};
                border-radius: 8px;
                padding: 12px 14px;
                font-size: 13.5px;
                font-weight: 800;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #D1EFEA;
                border: 2px solid {BRAND_TEAL};
            }}
        """)
        self.btn_real.clicked.connect(lambda: self._select_type("REAL"))
        cards_row.addWidget(self.btn_real, 1)

        self.btn_virtual = QPushButton(f"Versement Virtuel\n{format_money(self.virtual_balance)} DA")
        self.btn_virtual.setObjectName("BtnChooseVersementVirtual")
        self.btn_virtual.setIcon(get_duotone_icon("return_arrow", 24))
        self.btn_virtual.setIconSize(QSize(24, 24))
        self.btn_virtual.setCursor(Qt.PointingHandCursor)
        self.btn_virtual.setMinimumHeight(86)
        self.btn_virtual.setStyleSheet(f"""
            QPushButton {{
                background-color: {STATUS_INFO_BG};
                color: {STATUS_INFO};
                border: 1.5px solid {STATUS_INFO_BORDER};
                border-radius: 8px;
                padding: 12px 14px;
                font-size: 13.5px;
                font-weight: 800;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #DBEAFE;
                border: 2px solid {STATUS_INFO};
            }}
        """)
        self.btn_virtual.clicked.connect(lambda: self._select_type("VIRTUAL"))
        cards_row.addWidget(self.btn_virtual, 1)

        layout.addLayout(cards_row)

        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setStyleSheet(SLATE_OUTLINE_QSS)
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)
        layout.addLayout(footer)

    def _select_type(self, versement_type: str) -> None:
        self.selected_type = versement_type
        self.accept()


class VersementAmountApplyDialog(QDialog):
    """Second dialog: enter deduction amount and show client's remaining balance clearly."""

    def __init__(
        self,
        client_name: str,
        versement_type: str,
        available_balance: float,
        order_due: float,
        initial_amount: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.client_name = str(client_name or "").strip() or "Client"
        self.versement_type = "VIRTUAL" if str(versement_type).upper() == "VIRTUAL" else "REAL"
        self.type_label = "Versement Virtuel" if self.versement_type == "VIRTUAL" else "Versement Réel"
        self.available_balance = max(0.0, float(available_balance or 0.0))
        self.order_due = max(0.0, float(order_due or 0.0))
        self.applied_amount: float = 0.0

        self.setWindowTitle(f"Montant à déduire — {self.type_label}")
        self.setFixedWidth(460)
        self.setModal(True)
        self._init_ui(initial_amount)
        _center_dialog_on_screen(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _center_dialog_on_screen(self)

    def _init_ui(self, initial_amount: float) -> None:
        self.setObjectName("VersementAmountApplyDialog")
        self.setStyleSheet(f"""
            QDialog#VersementAmountApplyDialog {{
                background-color: {CARD_BG};
            }}
            QDialog#VersementAmountApplyDialog QLabel {{
                border: none;
                background: transparent;
                color: {TEXT_PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(f"Utiliser : {self.type_label}")
        title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {BRAND_TEAL};")
        layout.addWidget(title)

        summary_card = QFrame()
        summary_card.setObjectName("VersementApplySummaryCard")
        summary_card.setStyleSheet(f"""
            QFrame#VersementApplySummaryCard {{
                background-color: {SUBTLE_BG};
                border: 1px solid #E2E8F0;
                border-radius: 6px;
            }}
            QFrame#VersementApplySummaryCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        s_layout = QVBoxLayout(summary_card)
        s_layout.setContentsMargins(12, 10, 12, 10)
        s_layout.setSpacing(4)

        lbl_info = QLabel(
            f"Client : <b>{self.client_name}</b><br>"
            f"Solde {self.type_label} disponible : <b style='color:{BRAND_TEAL};'>{format_money(self.available_balance)} DA</b><br>"
            f"Montant à payer sur le bon : <b>{format_money(self.order_due)} DA</b>"
        )
        lbl_info.setStyleSheet(f"font-size: 12.5px; color: {TEXT_BODY}; line-height: 1.4;")
        s_layout.addWidget(lbl_info)
        layout.addWidget(summary_card)

        lbl_input = QLabel("Montant à déduire pour ce paiement (DA) :")
        lbl_input.setStyleSheet(f"font-size: 12.5px; font-weight: 700; color: {TEXT_BODY};")
        layout.addWidget(lbl_input)

        amt_row = QHBoxLayout()
        amt_row.setSpacing(8)

        max_applicable = max(0.0, min(self.available_balance, self.order_due))
        default_val = initial_amount if initial_amount > 0 else max_applicable
        default_txt = str(int(default_val)) if float(default_val).is_integer() else f"{default_val:.2f}"

        self.txt_amount = QLineEdit(default_txt if default_val > 0 else "0")
        self.txt_amount.setObjectName("TxtVersementDeductAmount")
        self.txt_amount.setFixedHeight(44)
        self.txt_amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.txt_amount.setStyleSheet(
            INPUT_QSS + f"QLineEdit {{ font-size: 20px; font-weight: 800; color: {TEXT_PRIMARY}; }}"
        )
        self.txt_amount.textChanged.connect(self._recalculate_preview)
        self.txt_amount.returnPressed.connect(self._confirm)
        self.txt_amount.selectAll()
        amt_row.addWidget(self.txt_amount, 1)

        self.btn_max = QPushButton("Max")
        self.btn_max.setCursor(Qt.PointingHandCursor)
        self.btn_max.setFixedHeight(44)
        self.btn_max.setStyleSheet(SLATE_OUTLINE_QSS)
        self.btn_max.clicked.connect(self._fill_max)
        amt_row.addWidget(self.btn_max)
        layout.addLayout(amt_row)

        # Prominent client remaining balance card (الباقي)
        rem_card = QFrame()
        rem_card.setObjectName("VersementRemainingBalanceCard")
        rem_card.setStyleSheet(f"""
            QFrame#VersementRemainingBalanceCard {{
                background-color: {BRAND_TEAL_TINT};
                border: none;
                border-left: 3px solid {BRAND_TEAL};
                border-radius: 6px;
            }}
            QFrame#VersementRemainingBalanceCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        r_layout = QVBoxLayout(rem_card)
        r_layout.setContentsMargins(12, 10, 12, 10)
        r_layout.setSpacing(4)

        self.lbl_client_remaining = QLabel("")
        self.lbl_client_remaining.setObjectName("LblClientRemainingAfterVersement")
        self.lbl_client_remaining.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {BRAND_TEAL};"
        )
        r_layout.addWidget(self.lbl_client_remaining)

        self.lbl_order_remaining = QLabel("")
        self.lbl_order_remaining.setObjectName("LblOrderRemainingAfterVersement")
        self.lbl_order_remaining.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {TEXT_BODY};"
        )
        r_layout.addWidget(self.lbl_order_remaining)
        layout.addWidget(rem_card)

        self.lbl_error = QLabel("")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {STATUS_DANGER};")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setStyleSheet(SLATE_OUTLINE_QSS)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton("Appliquer ce montant")
        self.btn_confirm.setObjectName("BtnConfirmVersementApply")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setFixedHeight(40)
        self.btn_confirm.setStyleSheet(PRIMARY_CTA_QSS)
        self.btn_confirm.clicked.connect(self._confirm)
        btn_row.addWidget(self.btn_confirm)
        layout.addLayout(btn_row)

        self._recalculate_preview()

    def _fill_max(self) -> None:
        max_val = max(0.0, min(self.available_balance, self.order_due))
        self.txt_amount.setText(str(int(max_val)) if max_val.is_integer() else f"{max_val:.2f}")
        self.txt_amount.setFocus()
        self.txt_amount.selectAll()

    def _recalculate_preview(self) -> None:
        amt = _parse_decimal_input(self.txt_amount.text())
        rem_client = max(0.0, self.available_balance - amt)
        rem_order = max(0.0, self.order_due - amt)

        self.lbl_client_remaining.setText(
            f"Solde client restant (الباقي) : {format_money(rem_client)} DA"
        )
        self.lbl_order_remaining.setText(
            f"Reste à payer sur la commande : {format_money(rem_order)} DA"
        )

        err_msg = ""
        if self.available_balance <= 0.0:
            err_msg = f"Le solde {self.type_label} du client est à 0,00 DA."
        elif amt <= 0.0:
            err_msg = "Veuillez saisir un montant strictement supérieur à 0 DA."
        elif amt > self.available_balance + 0.01:
            err_msg = (
                f"Le montant dépasse le solde {self.type_label} disponible "
                f"({format_money(self.available_balance)} DA)."
            )
        elif amt > self.order_due + 0.01:
            err_msg = (
                f"Le montant dépasse le montant de la commande "
                f"({format_money(self.order_due)} DA)."
            )

        if err_msg:
            self.lbl_client_remaining.setStyleSheet(
                f"font-size: 15px; font-weight: 800; color: {STATUS_DANGER};"
            )
            self.lbl_error.setText(err_msg)
            self.lbl_error.setVisible(True)
            self.btn_confirm.setEnabled(False)
        else:
            self.lbl_client_remaining.setStyleSheet(
                f"font-size: 15px; font-weight: 800; color: {STATUS_SUCCESS};"
            )
            self.lbl_error.setVisible(False)
            self.btn_confirm.setEnabled(True)

    def _confirm(self) -> None:
        self._recalculate_preview()
        if not self.btn_confirm.isEnabled():
            return
        self.applied_amount = round(_parse_decimal_input(self.txt_amount.text()), 2)
        self.accept()
