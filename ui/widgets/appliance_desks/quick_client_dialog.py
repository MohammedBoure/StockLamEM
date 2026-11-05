# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/quick_client_dialog.py
=================================================
Fast modal dialog to register new retail or wholesale clients on-the-fly directly
from the Order Desk (Bureau des Commandes) without navigating away.
Aligned with the StockLam #007572 visual theme and design standards.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ui.icons import get_duotone_icon


class QuickClientDialog(QDialog):
    """Sleek modal dialog for creating a client in seconds directly from Order Desk."""

    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.created_client: Optional[Dict[str, Any]] = None
        self.setWindowTitle("Nouveau Client Rapide")
        self.setFixedWidth(440)
        self.setModal(True)
        self._init_ui()

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
            QLineEdit, QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                color: #2C3E50;
                min-height: 28px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1.5px solid #007572;
                background-color: #FFFFFF;
            }
            QPushButton#SaveBtn {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                min-height: 32px;
            }
            QPushButton#SaveBtn:hover {
                background-color: #005A57;
            }
            QPushButton#SaveBtn:pressed {
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
                min-height: 32px;
            }
            QPushButton#CancelBtn:hover {
                background-color: #F8FAFC;
                border-color: #ADB5BD;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header with icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("users", 20).pixmap(20, 20))
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Création Rapide d'un Client")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #007572;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Form fields grid
        form_grid = QGridLayout()
        form_grid.setVerticalSpacing(10)
        form_grid.setHorizontalSpacing(10)

        # 1. Nom
        form_grid.addWidget(QLabel("Nom complet / Raison Sociale * :"), 0, 0)
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ex: SARL Electro Djazair, Amine Benali...")
        form_grid.addWidget(self.txt_name, 0, 1)

        # 2. Téléphone
        form_grid.addWidget(QLabel("Numéro de Téléphone :"), 1, 0)
        self.txt_phone = QLineEdit()
        self.txt_phone.setPlaceholderText("Ex: 0550 12 34 56")
        form_grid.addWidget(self.txt_phone, 1, 1)

        # 3. Adresse
        form_grid.addWidget(QLabel("Adresse / Ville :"), 2, 0)
        self.txt_address = QLineEdit()
        self.txt_address.setPlaceholderText("Ex: Bab Ezzouar, Alger")
        form_grid.addWidget(self.txt_address, 2, 1)

        # 4. Catégorie Tarifaire
        form_grid.addWidget(QLabel("Tarif Client :"), 3, 0)
        self.cbo_tier = QComboBox()
        self.cbo_tier.addItem("Prix_1 (Prix Public / Comptoir)", "Prix_1")
        self.cbo_tier.addItem("Prix_2 (Demi-Gros / Revendeur)", "Prix_2")
        self.cbo_tier.addItem("Prix_3 (Grossiste B2B)", "Prix_3")
        self.cbo_tier.addItem("Prix_4 (Partenaire Privilégié)", "Prix_4")
        form_grid.addWidget(self.cbo_tier, 3, 1)

        layout.addLayout(form_grid)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setObjectName("CancelBtn")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Enregistrer le Client")
        btn_save.setObjectName("SaveBtn")
        btn_save.setIcon(get_duotone_icon("users", 14))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        # Enter in inputs triggers save
        self.txt_name.returnPressed.connect(self._on_save)
        self.txt_phone.returnPressed.connect(self._on_save)
        self.txt_address.returnPressed.connect(self._on_save)

    def _on_save(self) -> None:
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Champ Requis", "Veuillez saisir le nom du client.")
            self.txt_name.setFocus()
            return

        phone = self.txt_phone.text().strip()
        address = self.txt_address.text().strip()
        tier = self.cbo_tier.currentData() or "Prix_1"

        client_id = None
        if self.data_manager and hasattr(self.data_manager, "clients"):
            try:
                client_id = self.data_manager.clients.add_client(
                    name=name,
                    phone=phone or None,
                    address=address or None,
                    price_tier=tier,
                )
            except Exception as err:
                QMessageBox.critical(self, "Erreur Base de Données", f"Impossible d'enregistrer le client :\n{err}")
                return

        self.created_client = {
            "Client_ID": client_id,
            "Client_Name": name,
            "Phone": phone,
            "Address": address,
            "Price_Tier": tier,
        }
        self.accept()
