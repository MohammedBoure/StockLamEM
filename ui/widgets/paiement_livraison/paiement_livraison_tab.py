# -*- coding: utf-8 -*-
"""Dedicated management workspace for the independent Paiement Livraison navbar section."""

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget

from ui.widgets.versement.bon_payments_workspace import BonPaymentsWorkspaceWidget


class PaiementLivraisonTab(BonPaymentsWorkspaceWidget):
    """Main Paiement Livraison page mirroring VersementTab for BON_LIVRAISON orders."""

    def __init__(
        self,
        data_manager: Any = None,
        current_user: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(
            data_manager=data_manager,
            current_user=current_user,
            bond_type="BON_LIVRAISON",
            title="Gestion des Paiements Livraison",
            subtitle="Suivi des bons de livraison, ajout direct d'un paiement et modification des montants versés",
            icon_name="truck_delivery",
            add_button_text="Paiement",
            add_dialog_title="Ajouter un Paiement Livraison",
            manage_dialog_title="Gérer les Paiements du Bon de Livraison",
            parent=parent,
        )
