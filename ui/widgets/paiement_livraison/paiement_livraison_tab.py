# -*- coding: utf-8 -*-
"""Minimal placeholder view for the Paiement Livraison navbar section."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.icons import get_duotone_icon


class PaiementLivraisonTab(QWidget):
    """Dedicated placeholder page for the Paiement Livraison sidebar entry."""

    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("PaiementLivraisonWorkspace")
        self.setStyleSheet(
            "QWidget#PaiementLivraisonWorkspace { background-color: #F8FAFC; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("PaiementLivraisonPlaceholderCard")
        card.setMaximumWidth(460)
        card.setStyleSheet(
            "QFrame#PaiementLivraisonPlaceholderCard {"
            "  background-color: #FFFFFF;"
            "  border: 1px solid #E2E8F0;"
            "  border-radius: 12px;"
            "}"
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel(card)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(get_duotone_icon("truck_delivery", 40).pixmap(40, 40))

        self.lbl_title = QLabel("Paiement Livraison", card)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #0F172A;"
        )

        self.lbl_subtitle = QLabel(
            "Interface Paiement Livraison prête dans la barre de navigation.\n"
            "Le contenu détaillé sera ajouté prochainement.",
            card,
        )
        self.lbl_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_subtitle.setWordWrap(True)
        self.lbl_subtitle.setStyleSheet(
            "font-size: 13px; color: #64748B;"
        )

        card_layout.addWidget(icon_label)
        card_layout.addWidget(self.lbl_title)
        card_layout.addWidget(self.lbl_subtitle)
        root.addWidget(card)
