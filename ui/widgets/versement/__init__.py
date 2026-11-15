# -*- coding: utf-8 -*-
"""Dedicated Versement workspace UI module (Navbar: Versement)."""

from .bon_payments_dialogs import BonPaymentAddDialog, BonPaymentsManageDialog
from .bon_payments_workspace import BonPaymentsWorkspaceWidget
from .versement_tab import VersementTab

__all__ = [
    "VersementTab",
    "BonPaymentsWorkspaceWidget",
    "BonPaymentAddDialog",
    "BonPaymentsManageDialog",
]
