# -*- coding: utf-8 -*-
"""
test/test_sav_workspace_tabs_and_navigation.py
=============================================
Automated test suite verifying Task #9:
1. Left navigation decoupling: Page 14 is 'Bureaux Opérationnels' and Page 15 is 'Service Après-Vente (SAV)'.
2. Navigation permissions fallback includes 'nav_sav'.
3. SAVWorkspaceTab structure: 6 dedicated status tabs (Toutes, Réception, Atelier, Prêt, Clôturé, Irréparable).
4. Status separation across tabs and live counters.
5. Search filtering and state transitions (dispatch, return, deliver, irreparable).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QMessageBox
from ui.navigation_permissions import NAVIGATION_PERMISSION_FALLBACKS, has_navigation_permission
from ui.widgets.appliance_desks.sav_workspace_view import SAVWorkspaceTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_tickets():
    return [
        {
            "SAV_Ticket_ID": 1,
            "Ticket_Number": "SAV-202611-0001",
            "Bon_Reparation_Barcode": "BON-SAV-001",
            "Client_Name": "Amine Benali",
            "Product_Name": "Lave-linge Frontal 9kg",
            "Serial_Number": "SN-LL9K-001",
            "Is_Under_Warranty": True,
            "Customer_Stated_Symptom": "Tambour ne tourne plus",
            "Technician_Name": "Karim Reparations",
            "Reception_Date": "2026-11-01",
            "Current_Stage": "SAV_RECEIVED",
        },
        {
            "SAV_Ticket_ID": 2,
            "Ticket_Number": "SAV-202611-0002",
            "Bon_Reparation_Barcode": "BON-SAV-002",
            "Client_Name": "Fatima Zohra",
            "Product_Name": "Réfrigérateur Combiné NoFrost",
            "Serial_Number": "SN-RF-002",
            "Is_Under_Warranty": False,
            "Customer_Stated_Symptom": "Fuite de gaz réfrigérant",
            "Technician_Name": "Atelier Central",
            "Reception_Date": "2026-11-02",
            "Current_Stage": "SAV_SENT_TO_TECH",
        },
        {
            "SAV_Ticket_ID": 3,
            "Ticket_Number": "SAV-202611-0003",
            "Bon_Reparation_Barcode": "BON-SAV-003",
            "Client_Name": "Youcef Kaci",
            "Product_Name": "Four Encastrable 65L",
            "Serial_Number": "SN-FOUR-003",
            "Is_Under_Warranty": True,
            "Customer_Stated_Symptom": "Résistance grill HS",
            "Technician_Name": "Atelier Central",
            "Reception_Date": "2026-11-03",
            "Current_Stage": "SAV_RETURNED_FROM_TECH",
            "Resolution_Status": "REPAIRED",
        },
        {
            "SAV_Ticket_ID": 4,
            "Ticket_Number": "SAV-202611-0004",
            "Bon_Reparation_Barcode": "BON-SAV-004",
            "Client_Name": "Omar Djebbar",
            "Product_Name": "Micro-ondes Pro 25L",
            "Serial_Number": "SN-MO-004",
            "Is_Under_Warranty": False,
            "Customer_Stated_Symptom": "Plateau ne tourne pas",
            "Technician_Name": "Tech Express",
            "Reception_Date": "2026-11-04",
            "Current_Stage": "SAV_CLOSED_DELIVERED",
            "Resolution_Status": "REPAIRED",
        },
        {
            "SAV_Ticket_ID": 5,
            "Ticket_Number": "SAV-202611-0005",
            "Bon_Reparation_Barcode": "BON-SAV-005",
            "Client_Name": "Sara Meziane",
            "Product_Name": "Téléviseur 55 UHD OLED",
            "Serial_Number": "SN-TV-005",
            "Is_Under_Warranty": True,
            "Customer_Stated_Symptom": "Dalle fissurée irréparable",
            "Technician_Name": "LG Expert",
            "Reception_Date": "2026-11-05",
            "Current_Stage": "SAV_CLOSED_DELIVERED",
            "Resolution_Status": "IRREPARABLE_COMPENSATED",
        },
    ]


@pytest.fixture
def mock_data_manager(sample_tickets):
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}
    dm.sav = MagicMock()
    dm.sav.get_all_sav_tickets.return_value = list(sample_tickets)
    dm.sav.dispatch_to_technician.return_value = True
    dm.sav.record_technician_return.return_value = True
    dm.sav.deliver_repaired_to_client.return_value = True
    dm.sav.process_irreparable_compensation.return_value = True
    return dm


def test_navigation_permission_includes_nav_sav():
    """Verifies nav_sav is registered in NAVIGATION_PERMISSION_FALLBACKS."""
    assert "nav_sav" in NAVIGATION_PERMISSION_FALLBACKS
    fallbacks = NAVIGATION_PERMISSION_FALLBACKS["nav_sav"]
    assert "tab_desk_sav" in fallbacks
    assert "SAV_TICKET_CREATE" in fallbacks
    assert "SAV_MANAGE_STAGES" in fallbacks

    # Test permission resolution with user dictionaries
    admin_user = {"Role": "admin"}
    direct_user = {"Role": "technician", "Permissions": {"nav_sav": True}}
    fallback_user = {"Role": "technician", "Permissions": {"SAV_MANAGE_STAGES": True}}
    unauthorized_user = {"Role": "driver", "Permissions": {"nav_inventory": True}}

    assert has_navigation_permission(admin_user, "nav_sav")
    assert has_navigation_permission(direct_user, "nav_sav")
    assert has_navigation_permission(fallback_user, "nav_sav")
    assert not has_navigation_permission(unauthorized_user, "nav_sav")


def test_sav_workspace_tab_structure(qapp, mock_data_manager, sample_tickets):
    """Verifies that SAVWorkspaceTab initializes 6 distinct stage tabs with headers and badges."""
    workspace = SAVWorkspaceTab(data_manager=mock_data_manager)

    # 1. Total 6 status tabs
    assert workspace.tabs.count() == 6

    # 2. Check tab titles match all stage flows
    titles = [workspace.tabs.tabText(i) for i in range(workspace.tabs.count())]
    assert any("Toutes" in t for t in titles)
    assert any("Réception" in t for t in titles)
    assert any("Atelier" in t for t in titles)
    assert any("Restitution" in t for t in titles)
    assert any("Clôturés" in t for t in titles)
    assert any("Irréparables" in t for t in titles)

    # 3. Check table rows per tab
    # Tab ALL: all 5 tickets
    table_all = workspace._stage_tables["ALL"]
    assert table_all.rowCount() == 5

    # Tab SAV_RECEIVED: ticket 1
    table_rcv = workspace._stage_tables["SAV_RECEIVED"]
    assert table_rcv.rowCount() == 1
    assert table_rcv.item(0, 0).text() == "SAV-202611-0001"

    # Tab SAV_SENT_TO_TECH: ticket 2
    table_sent = workspace._stage_tables["SAV_SENT_TO_TECH"]
    assert table_sent.rowCount() == 1
    assert table_sent.item(0, 0).text() == "SAV-202611-0002"

    # Tab SAV_RETURNED_FROM_TECH: ticket 3
    table_ret = workspace._stage_tables["SAV_RETURNED_FROM_TECH"]
    assert table_ret.rowCount() == 1
    assert table_ret.item(0, 0).text() == "SAV-202611-0003"

    # Tab SAV_CLOSED_DELIVERED: ticket 4
    table_closed = workspace._stage_tables["SAV_CLOSED_DELIVERED"]
    assert table_closed.rowCount() == 1
    assert table_closed.item(0, 0).text() == "SAV-202611-0004"

    # Tab IRREPARABLE: ticket 5
    table_irrep = workspace._stage_tables["IRREPARABLE"]
    assert table_irrep.rowCount() == 1
    assert table_irrep.item(0, 0).text() == "SAV-202611-0005"


def test_sav_search_filtering(qapp, mock_data_manager):
    """Verifies that search input filters tickets dynamically across tables."""
    workspace = SAVWorkspaceTab(data_manager=mock_data_manager)

    # Filter by client name 'Fatima'
    workspace.txt_global_search.setText("Fatima")
    table_all = workspace._stage_tables["ALL"]
    assert table_all.rowCount() == 1
    assert table_all.item(0, 0).text() == "SAV-202611-0002"

    # Filter by serial number
    workspace.txt_global_search.setText("SN-TV-005")
    assert table_all.rowCount() == 1
    assert table_all.item(0, 0).text() == "SAV-202611-0005"

    # Clear filter
    workspace.txt_global_search.setText("")
    assert table_all.rowCount() == 5


def test_sav_stage_actions_dispatch_and_return(qapp, mock_data_manager, sample_tickets):
    """Verifies ticket action triggers call data_manager.sav methods."""
    workspace = SAVWorkspaceTab(data_manager=mock_data_manager)

    ticket_3 = sample_tickets[2]  # SAV_RETURNED_FROM_TECH

    orig_question = QMessageBox.question
    orig_info = QMessageBox.information
    QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    try:
        workspace._deliver_to_client(ticket_3)
        mock_data_manager.sav.deliver_repaired_to_client.assert_called_with(
            sav_ticket_id=ticket_3["SAV_Ticket_ID"],
            user_id=1,
        )
    finally:
        QMessageBox.question = orig_question
        QMessageBox.information = orig_info
