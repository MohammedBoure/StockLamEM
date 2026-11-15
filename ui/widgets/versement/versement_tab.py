# -*- coding: utf-8 -*-
"""Dedicated management workspace for the independent Versement navbar section."""

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget

from .bon_payments_workspace import BonPaymentsWorkspaceWidget


class VersementTab(BonPaymentsWorkspaceWidget):
    """Main Versement page listing all Bons de versement with add & edit actions."""

    def __init__(
        self,
        data_manager: Any = None,
        current_user: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(
            data_manager=data_manager,
            current_user=current_user,
            bond_type="BON_VERSEMENT",
            title="Gestion des Bons de Versement",
            subtitle="Liste des bons de versement, ajout direct d'un versement et modification des paiements",
            icon_name="kpi_wallet",
            add_button_text="Versement",
            add_dialog_title="Ajouter un Versement",
            manage_dialog_title="Gérer les Versements du Bon",
            parent=parent,
        )
