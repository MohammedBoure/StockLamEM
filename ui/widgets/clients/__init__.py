# -*- coding: utf-8 -*-
"""
Dedicated Clients Directory UI Module (Navbar: Clients).
"""

from .clients_tab import ClientsTab
from .client_statement_dialog import ClientStatementDialog, TransactionDetailsDialog
from .client_versements_dialog import ClientVersementsDialog

__all__ = [
    "ClientsTab",
    "ClientStatementDialog",
    "TransactionDetailsDialog",
    "ClientVersementsDialog",
]
