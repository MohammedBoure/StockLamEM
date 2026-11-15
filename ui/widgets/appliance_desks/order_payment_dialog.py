# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/order_payment_dialog.py
==================================================
Centered confirmation dialog shown immediately after customer selection for
Order Desk orders (Paiement complet, Paiement à crédit, Paiement à la livraison).
Displays the selected payment method and an editable shipping/delivery location
field pre-filled automatically from mobile app session data when available.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
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


_METHOD_OPTIONS = [
    ("BON_C", "Paiement complet"),
    ("BON_CREDIT", "Paiement à crédit"),
    ("BON_LIVRAISON", "Paiement à la livraison"),
]


class OrderPaymentConfirmationDialog(QDialog):
    """Centered popup dialog confirming Méthode de paiement and shipping location."""

    def __init__(
        self,
        bond_type: str = "BON_C",
        client_name: str = "Client Comptoir",
        total_ttc: float = 0.0,
        delivery_address: str = "",
        from_mobile: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._initial_bond_type = bond_type if bond_type in dict(_METHOD_OPTIONS) else "BON_C"
        self._client_name = str(client_name or "").strip() or "Client Comptoir"
        self._total_ttc = float(total_ttc or 0.0)
        self._initial_address = str(delivery_address or "").strip()
        self._from_mobile = bool(from_mobile and self._initial_address)

        self.result_info: Optional[Dict[str, Any]] = None
        self.method_buttons: Dict[str, QPushButton] = {}

        self.setWindowTitle("Méthode de paiement")
        self.setFixedWidth(480)
        self.setModal(True)
        self._init_ui()
        self._center_on_screen()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.adjustSize()
            self.move(geo.center() - self.rect().center())

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #2C3E50;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                color: #2C3E50;
                min-height: 32px;
            }
            QLineEdit:hover {
                border-color: #ADB5BD;
            }
            QLineEdit:focus {
                border: 1.5px solid #007572;
                background-color: #FFFFFF;
            }
            QPushButton#MethodChoiceBtn {
                background-color: #FFFFFF;
                color: #334155;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 8px 10px;
                min-height: 34px;
            }
            QPushButton#MethodChoiceBtn:hover {
                border-color: #007572;
                background-color: #F8FAFC;
            }
            QPushButton#MethodChoiceBtn:checked {
                background-color: #E8F8F5;
                color: #007572;
                border: 1.5px solid #007572;
                font-weight: 700;
            }
            QPushButton#ConfirmBtn {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                min-height: 34px;
            }
            QPushButton#ConfirmBtn:hover {
                background-color: #005A57;
            }
            QPushButton#ConfirmBtn:pressed {
                background-color: #003D3A;
            }
            QPushButton#CancelBtn {
                background-color: #FFFFFF;
                color: #495057;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 6px 16px;
                min-height: 34px;
            }
            QPushButton#CancelBtn:hover {
                background-color: #F8FAFC;
                border-color: #ADB5BD;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("payment", 20).pixmap(20, 20))
        hdr.addWidget(icon_lbl)

        title_lbl = QLabel("Confirmation — Méthode de paiement")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #007572;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Compact Client & Total Summary Strip
        summary_frame = QFrame()
        summary_frame.setObjectName("PaymentSummaryStrip")
        summary_frame.setStyleSheet("""
            QFrame#PaymentSummaryStrip {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-left: 3px solid #007572;
                border-radius: 4px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        s_lay = QHBoxLayout(summary_frame)
        s_lay.setContentsMargins(12, 8, 12, 8)
        self.lbl_client_summary = QLabel(self._client_name)
        self.lbl_client_summary.setStyleSheet("font-size: 12px; font-weight: 700; color: #1E293B;")
        s_lay.addWidget(self.lbl_client_summary)
        s_lay.addStretch()
        self.lbl_total_summary = QLabel(f"{format_money(self._total_ttc)} DA")
        self.lbl_total_summary.setStyleSheet("font-size: 13px; font-weight: 800; color: #007572;")
        s_lay.addWidget(self.lbl_total_summary)
        layout.addWidget(summary_frame)

        # Payment Method Options
        lbl_method = QLabel("Méthode de paiement :")
        layout.addWidget(lbl_method)

        method_row = QHBoxLayout()
        method_row.setSpacing(8)
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        for code, label in _METHOD_OPTIONS:
            btn = QPushButton(label)
            btn.setObjectName("MethodChoiceBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("bond_type", code)
            btn.setChecked(code == self._initial_bond_type)
            self._btn_group.addButton(btn)
            method_row.addWidget(btn, 1)
            self.method_buttons[code] = btn
        layout.addLayout(method_row)

        # Shipping / Delivery Location Field
        lbl_loc = QLabel("Lieu de livraison / Expédition :")
        layout.addWidget(lbl_loc)

        self.txt_shipping_location = QLineEdit()
        self.txt_shipping_location.setPlaceholderText("Adresse, wilaya ou lieu de livraison...")
        self.txt_shipping_location.setClearButtonEnabled(True)
        self.txt_shipping_location.setText(self._initial_address)
        layout.addWidget(self.txt_shipping_location)

        self.lbl_mobile_loc_hint = QLabel("Lieu pré-rempli depuis l'application mobile (modifiable).")
        self.lbl_mobile_loc_hint.setStyleSheet("font-size: 11px; font-weight: 600; color: #007572;")
        self.lbl_mobile_loc_hint.setVisible(self._from_mobile)
        layout.addWidget(self.lbl_mobile_loc_hint)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setObjectName("CancelBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton("Confirmer")
        self.btn_confirm.setObjectName("ConfirmBtn")
        self.btn_confirm.setDefault(True)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.clicked.connect(self._on_confirm)
        btn_row.addWidget(self.btn_confirm)

        layout.addLayout(btn_row)

    def selected_bond_type(self) -> str:
        checked = self._btn_group.checkedButton()
        if checked is not None:
            return str(checked.property("bond_type") or self._initial_bond_type)
        return self._initial_bond_type

    def _on_confirm(self) -> None:
        self.result_info = {
            "bond_type": self.selected_bond_type(),
            "delivery_address": self.txt_shipping_location.text().strip(),
        }
        self.accept()
