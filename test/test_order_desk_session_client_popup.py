# -*- coding: utf-8 -*-
"""
test/test_order_desk_session_client_popup.py
=============================================
Headless tests for Task #3 (Bureaux -> 1. Commandes):
- Verifies client search/input fields are removed from the main OrderDeskWidget UI.
- Verifies mobile sessions accept optional client_name, client_phone, and delivery_address,
  naming the session by client_name when provided and leaving it unnamed otherwise.
- Verifies executing any order action opens OrderClientDialog pre-populated with incoming
  app client details, allowing editing or switching to another client before submission.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from ui.widgets.appliance_desks.order_client_dialog import OrderClientDialog
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


@pytest.fixture(scope="module")
def qapp():
    os.environ["PYTEST_CURRENT_TEST"] = "1"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_dm():
    dm = MagicMock()
    dm.manufacturers.get_all_manufacturers.return_value = []
    dm.families.get_all_families.return_value = []
    dm.colors.get_all_colors.return_value = []
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Client Comptoir", "Phone": "", "Address": "", "Price_Tier": "Prix_1"},
        {"Client_ID": 2, "Client_Name": "Ali Benali", "Phone": "0550112233", "Address": "Alger", "Price_Tier": "Prix_1"},
        {"Client_ID": 3, "Client_Name": "Nadia Khelifi", "Phone": "0661445566", "Address": "Oran", "Price_Tier": "Prix_1"},
    ]
    dm.clients.add_client.return_value = 99
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "LG",
            "Product_Name": "Lave-Linge 9Kg",
            "Primary_Ref": "LG-9KG",
            "Color_Finish": "Inox",
            "Physical_Stock_Qty": 5,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 78000.0,
            "Price_1_TTC": 78000.0,
            "Purchase_Price_TTC": 60000.0,
        }
    ]
    dm.bonds.create_sales_order_draft.return_value = {
        "success": True,
        "order_id": 501,
        "order_number": "1-BC-2026-00501",
        "bond_type": "BON_C",
        "total_ttc": 78000.0,
        "scanner_session_id": "SESSION_2",
    }
    return dm


def test_main_desk_has_no_inline_client_or_delivery_inputs(qapp):
    dm = _make_dm()
    desk = OrderDeskWidget(dm)
    try:
        assert not hasattr(desk, "cbo_client")
        assert not hasattr(desk, "txt_delivery_addr")
        assert not hasattr(desk, "txt_client_search")
    finally:
        desk.deleteLater()


def test_mobile_session_naming_with_and_without_client_info(qapp):
    dm = _make_dm()
    desk = OrderDeskWidget(dm)
    try:
        # With client_name sent from mobile app
        snap_named = desk.create_mobile_session(
            client_name="Sami Mansour",
            client_phone="0770123456",
            delivery_address="Blida Centre",
            created_by="Mobile-1",
        )
        assert snap_named["label"] == "Sami Mansour"
        assert snap_named["client_name"] == "Sami Mansour"
        assert snap_named["client_phone"] == "0770123456"
        assert snap_named["delivery_address"] == "Blida Centre"

        # Without client info -> unnamed session
        snap_anon = desk.create_mobile_session(created_by="Mobile-1")
        assert snap_anon["label"].startswith("Session #")
        assert "Sami" not in snap_anon["label"]
        assert snap_anon["client_name"] == ""
        assert snap_anon["client_id"] is None
    finally:
        desk.deleteLater()


def test_popup_dialog_prefills_mobile_data_allows_edit_and_client_switch(qapp):
    dm = _make_dm()
    desk = OrderDeskWidget(dm)
    try:
        snap = desk.create_mobile_session(
            client_name="Karim Mobile",
            client_phone="0555001122",
            delivery_address="Tipaza Port",
        )
        sid = snap["session_id"]
        # Focus mobile session & add product
        for i in range(desk.session_tab_bar.count()):
            if desk.session_tab_bar.tabData(i) == sid:
                desk.session_tab_bar.setCurrentIndex(i)
                break
        desk.add_mobile_item_to_session(sid, product_id=101, quantity=1)

        # 1. Dialog directly pre-populates mobile app details and lets user modify them
        dlg = OrderClientDialog(
            data_manager=dm,
            clients_cache=desk._clients_cache,
            session_data=desk._sessions[sid],
            parent=desk,
        )
        assert dlg.mobile_banner.isVisibleTo(dlg) is True
        assert dlg.txt_client_name.text() == "Karim Mobile"
        assert dlg.txt_client_phone.text() == "0555001122"
        assert dlg.txt_delivery_addr.text() == "Tipaza Port"

        # Test switching via search to an existing client ("06614455" -> Nadia Khelifi)
        dlg.txt_client_search.setText("06614455")
        assert dlg.cbo_client.currentData() == 3
        assert dlg.txt_client_name.text() == "Nadia Khelifi"
        assert dlg.txt_delivery_addr.text() == "Oran"

        # Switch back to manual / mobile entry and edit phone & delivery location
        dlg.txt_client_search.clear()
        dlg.cbo_client.setCurrentIndex(0)
        assert dlg.cbo_client.currentData() is None
        dlg.txt_client_phone.setText("0555999888")
        dlg.txt_delivery_addr.setText("Tipaza Plage")
        dlg._on_confirm()

        assert dlg.result() == QDialog.Accepted
        assert dlg.selected_client_info["client_id"] == 99
        assert dlg.selected_client_info["client_name"] == "Karim Mobile"
        assert dlg.selected_client_info["client_phone"] == "0555999888"
        assert dlg.selected_client_info["delivery_address"] == "Tipaza Plage"
        dlg.deleteLater()

        # 2. Cancelling the popup on _submit_order aborts draft creation
        with patch.object(OrderClientDialog, "exec", return_value=QDialog.Rejected):
            desk._submit_order("BON_C")
        dm.bonds.create_sales_order_draft.assert_not_called()

        # 3. Accepting the popup on _submit_order forwards confirmed client & delivery info
        with patch.object(
            desk,
            "_prompt_order_client",
            return_value={
                "client_id": 99,
                "client_name": "Karim Mobile",
                "client_phone": "0555999888",
                "delivery_address": "Tipaza Plage",
            },
        ) as mock_prompt:
            with patch.object(QMessageBox, "information"):
                desk.btn_bon_c.click()

        mock_prompt.assert_called_once()
        dm.bonds.create_sales_order_draft.assert_called_once()
        kw = dm.bonds.create_sales_order_draft.call_args.kwargs
        assert kw["client_id"] == 99
        assert kw["delivery_address"] == "Tipaza Plage"
        assert kw["delivery_phone"] == "0555999888"
    finally:
        desk.deleteLater()
