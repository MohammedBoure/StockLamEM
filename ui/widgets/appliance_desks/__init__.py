# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/__init__.py
======================================
Exports for the Multi-Desk Electrical Appliance Store Operational Workflow UI.
"""

from .appliance_workflow_tab import ApplianceWorkflowTab
from .bon_pdf_export import export_order_bon_to_pdf
from .cashier_desk_view import AdminAuthModal, BonRetourDialog, CashierDeskWidget, ClientWalletDialog
from .dispatch_desk_view import DispatchDeskWidget
from .order_bons_dialog import OrderBonEditDialog, OrderDeskBonsDialog
from .order_desk_view import OrderDeskWidget
from .quick_client_dialog import QuickClientDialog
from .serial_batch_view import SerialBatchRegistryWidget
from ui.widgets.sav import IrreparableDefectModal, SAVKanbanWidget, SAVReceptionDialog, SAVWorkspaceTab

__all__ = [
    "ApplianceWorkflowTab",
    "OrderDeskWidget",
    "OrderDeskBonsDialog",
    "OrderBonEditDialog",
    "export_order_bon_to_pdf",
    "QuickClientDialog",
    "CashierDeskWidget",
    "ClientWalletDialog",
    "AdminAuthModal",
    "BonRetourDialog",
    "DispatchDeskWidget",
    "SAVKanbanWidget",
    "SAVWorkspaceTab",
    "SAVReceptionDialog",
    "IrreparableDefectModal",
    "SerialBatchRegistryWidget",
]
