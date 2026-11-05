# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/__init__.py
======================================
Exports for the Multi-Desk Electrical Appliance Store Operational Workflow UI.
"""

from .appliance_workflow_tab import ApplianceWorkflowTab
from .cashier_desk_view import AdminAuthModal, BonRetourDialog, CashierDeskWidget
from .dispatch_desk_view import DispatchDeskWidget
from .order_desk_view import OrderDeskWidget
from .quick_client_dialog import QuickClientDialog
from .sav_kanban_view import IrreparableDefectModal, SAVKanbanWidget, SAVReceptionDialog
from .sav_workspace_view import SAVWorkspaceTab
from .serial_batch_view import SerialBatchRegistryWidget

__all__ = [
    "ApplianceWorkflowTab",
    "OrderDeskWidget",
    "QuickClientDialog",
    "CashierDeskWidget",
    "AdminAuthModal",
    "BonRetourDialog",
    "DispatchDeskWidget",
    "SAVKanbanWidget",
    "SAVWorkspaceTab",
    "SAVReceptionDialog",
    "IrreparableDefectModal",
    "SerialBatchRegistryWidget",
]
