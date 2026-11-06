# -*- coding: utf-8 -*-
"""
Dedicated After-Sales Service & Repairs UI Module (Navbar: SAV).
"""

from .sav_kanban_view import IrreparableDefectModal, SAVKanbanWidget, SAVReceptionDialog
from .sav_workspace_view import SAVWorkspaceTab

__all__ = [
    "SAVWorkspaceTab",
    "SAVKanbanWidget",
    "SAVReceptionDialog",
    "IrreparableDefectModal",
]
