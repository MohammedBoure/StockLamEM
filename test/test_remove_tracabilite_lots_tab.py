# -*- coding: utf-8 -*-
"""
test/test_remove_tracabilite_lots_tab.py
========================================
Automated verification test suite for Task #2:
- Complete removal of 'Traçabilité & Lots' tab from Bureaux & SAV (ApplianceWorkflowTab).
- Guarantees exactly 4 desks remain: Commandes, Caisse, Sortie Magasin, and SAV.
- Verifies RBAC tab enabling works cleanly with the 4 tabs without index errors.
- Verifies cross-desk signals (order creation, caisse settlement, dispatch) execute safely without exceptions.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_data_manager():
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}
    dm.clients = MagicMock()
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Client Comptoir (Standard)", "Phone": "0550000000", "Address": "Alger"}
    ]
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "KGN39VLEB Combi NoFrost 368L",
            "Category_Name": "Gros Électroménager",
            "Color_Finish": "Inox",
            "Physical_Qty": 5,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 115000.0,
            "Barcode": "4242005198030",
        }
    ]
    return dm


def test_tracabilite_lots_tab_completely_removed(qapp, mock_data_manager):
    """Verifies that 'Traçabilité & Lots' is completely removed from Bureaux Opérationnels."""
    # Default is include_sav=False (3 operational desks)
    workflow = ApplianceWorkflowTab(data_manager=mock_data_manager)

    # 1. Must have exactly 3 operational tabs
    assert workflow.desk_tabs.count() == 3, f"Expected 3 tabs in Bureaux Opérationnels, found {workflow.desk_tabs.count()}"

    # 2. Check tab text
    titles = [workflow.desk_tabs.tabText(i) for i in range(workflow.desk_tabs.count())]
    for t in titles:
        assert "Traçabilité" not in t, f"Unexpected 'Traçabilité' in tab title: {t}"
        assert "Lots" not in t, f"Unexpected 'Lots' in tab title: {t}"

    assert "Commandes" in titles[0]
    assert "Caisse" in titles[1]
    assert "Sortie Magasin" in titles[2]

    # When include_sav=True, 4 desks exist
    workflow_sav = ApplianceWorkflowTab(data_manager=mock_data_manager, include_sav=True)
    assert workflow_sav.desk_tabs.count() == 4
    assert "SAV" in workflow_sav.desk_tabs.tabText(3)


def test_cross_desk_signals_safe_without_tracabilite_tab(qapp, mock_data_manager):
    """Verifies cross-desk signals operate properly and smoothly without the 5th tab."""
    workflow = ApplianceWorkflowTab(data_manager=mock_data_manager)

    # Trigger events that used to notify batch_registry_desk
    workflow._on_order_created({"order_id": 1})
    workflow._on_caisse_settled("CMD-001", "BON_C")
    workflow._on_dispatch_completed("CMD-001", ["SN12345"])
    workflow._on_catalog_updated()
    workflow.refresh_all_desks()


def test_rbac_permissions_span_tabs_cleanly(qapp, mock_data_manager):
    """Verifies RBAC permission rules align with the tabs without index errors."""
    # When include_sav=False (3 desks)
    workflow = ApplianceWorkflowTab(data_manager=mock_data_manager, include_sav=False)

    # User with only Caisse permission
    workflow.apply_rbac_permissions({"CAISSE_SETTLE_CASH"})
    assert not workflow.desk_tabs.isTabEnabled(0)
    assert workflow.desk_tabs.isTabEnabled(1)
    assert not workflow.desk_tabs.isTabEnabled(2)

    # Admin user
    workflow.apply_rbac_permissions({"admin"})
    for i in range(3):
        assert workflow.desk_tabs.isTabEnabled(i)

    # When include_sav=True (4 desks)
    workflow_4 = ApplianceWorkflowTab(data_manager=mock_data_manager, include_sav=True)
    workflow_4.apply_rbac_permissions({"SAV_TICKET_CREATE"})
    assert not workflow_4.desk_tabs.isTabEnabled(0)
    assert not workflow_4.desk_tabs.isTabEnabled(1)
    assert not workflow_4.desk_tabs.isTabEnabled(2)
    assert workflow_4.desk_tabs.isTabEnabled(3)
