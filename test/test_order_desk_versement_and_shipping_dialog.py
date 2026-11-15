# -*- coding: utf-8 -*-
"""
test/test_order_desk_versement_and_shipping_dialog.py
=====================================================
Headless tests for Task #4 (Bureaux -> 1. Commandes):
1. Versement (BON_VERSEMENT) shows ONLY the client selection popup (OrderClientDialog),
   skips any payment method / amount prompt in Commandes, leaving amount entry strictly
   in Caisse (CashierDeskWidget).
2. Regular order confirmations (BON_C, BON_CREDIT, BON_LIVRAISON) open the centered
   Méthode de paiement confirmation dialog (OrderPaymentConfirmationDialog) right after
   OrderClientDialog, pre-populating shipping/delivery location sent from mobile app
   when available and passing confirmed edits to draft creation.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from ui.widgets.appliance_desks.order_client_dialog import OrderClientDialog
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.appliance_desks.order_payment_dialog import OrderPaymentConfirmationDialog


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
        {"Client_ID": 5, "Client_Name": "Amine Saadi", "Phone": "0550112233", "Address": "Rouiba, Alger", "Price_Tier": "Prix_1"},
    ]
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 201,
            "Brand_Mark": "Condor",
            "Product_Name": "Climatiseur 18000 BTU",
            "Primary_Ref": "CS-18",
            "Color_Finish": "Blanc",
            "Physical_Stock_Qty": 4,
            "Available_Theoretical_Qty": 4,
            "Unit_Price_TTC": 92000.0,
            "Price_1_TTC": 92000.0,
            "Purchase_Price_TTC": 75000.0,
        }
    ]
    dm.bonds.create_sales_order_draft.side_effect = lambda **kw: {
        "success": True,
        "order_id": 700,
        "order_number": "4-VRS-2026-00700" if kw.get("bond_type") == "BON_VERSEMENT" else "1-BC-2026-00700",
        "bond_type": kw.get("bond_type", "BON_C"),
        "total_ttc": 92000.0,
    }
    return dm


def test_versement_shows_only_client_dialog_without_payment_or_amount_popup(qapp):
    dm = _make_dm()
    desk = OrderDeskWidget(dm)
    try:
        desk.refresh_catalog()
        desk._add_product_to_session(desk._active_session_id, desk._catalog_filtered_items[0])

        # Verify OrderClientDialog displays versement notice & no amount field when BON_VERSEMENT
        client_dlg = OrderClientDialog(
            data_manager=dm,
            clients_cache=desk._clients_cache,
            session_data=desk._sessions[desk._active_session_id],
            bond_type="BON_VERSEMENT",
            parent=desk,
        )
        assert client_dlg.versement_banner.isVisibleTo(client_dlg) is True
        client_dlg.deleteLater()

        with patch.object(
            desk,
            "_prompt_order_client",
            return_value={
                "client_id": 5,
                "client_name": "Amine Saadi",
                "client_phone": "0550112233",
                "delivery_address": "Rouiba, Alger",
            },
        ) as mock_client, patch.object(
            desk,
            "_prompt_payment_confirmation",
        ) as mock_pay, patch.object(QMessageBox, "information"):
            desk.btn_versement.click()

        mock_client.assert_called_once()
        mock_pay.assert_not_called()
        dm.bonds.create_sales_order_draft.assert_called_once()
        assert dm.bonds.create_sales_order_draft.call_args.kwargs["bond_type"] == "BON_VERSEMENT"
    finally:
        desk.deleteLater()


def test_order_payment_dialog_sequence_prefills_mobile_shipping_and_centers(qapp):
    dm = _make_dm()
    desk = OrderDeskWidget(dm)
    try:
        snap = desk.create_mobile_session(
            client_name="Meriem Ziani",
            client_phone="0770889900",
            delivery_address="Chéraga, Alger",
        )
        sid = snap["session_id"]
        for i in range(desk.session_tab_bar.count()):
            if desk.session_tab_bar.tabData(i) == sid:
                desk.session_tab_bar.setCurrentIndex(i)
                break
        desk.add_mobile_item_to_session(sid, product_id=201, quantity=1)

        # 1. Verify centered dialog layout & mobile shipping location pre-fill
        pay_dlg = OrderPaymentConfirmationDialog(
            bond_type="BON_LIVRAISON",
            client_name="Meriem Ziani",
            total_ttc=92000.0,
            delivery_address=desk._sessions[sid]["delivery_address"],
            from_mobile=True,
            parent=desk,
        )
        pay_dlg._center_on_screen()
        assert pay_dlg.windowTitle() == "Méthode de paiement"
        assert pay_dlg.selected_bond_type() == "BON_LIVRAISON"
        assert pay_dlg.txt_shipping_location.text() == "Chéraga, Alger"
        assert pay_dlg.lbl_mobile_loc_hint.isVisibleTo(pay_dlg) is True

        screen = pay_dlg.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            sc_center = screen.availableGeometry().center()
            dlg_center = pay_dlg.geometry().center()
            assert abs(dlg_center.x() - sc_center.x()) <= 25
            assert abs(dlg_center.y() - sc_center.y()) <= 25

        # User edits shipping location & switches method
        pay_dlg.txt_shipping_location.setText("Dely Ibrahim, Alger")
        pay_dlg.method_buttons["BON_C"].setChecked(True)
        pay_dlg._on_confirm()
        assert pay_dlg.result() == QDialog.Accepted
        assert pay_dlg.result_info == {
            "bond_type": "BON_C",
            "delivery_address": "Dely Ibrahim, Alger",
        }
        pay_dlg.deleteLater()

        # 2. Sequence abort on Step 2 cancel does not create any bond
        call_order = []
        with patch.object(
            desk,
            "_prompt_order_client",
            side_effect=lambda *a, **k: (
                call_order.append("client"),
                {
                    "client_id": 5,
                    "client_name": "Meriem Ziani",
                    "client_phone": "0770889900",
                    "delivery_address": "Chéraga, Alger",
                },
            )[1],
        ), patch.object(OrderPaymentConfirmationDialog, "exec", return_value=QDialog.Rejected):
            desk._submit_order("BON_C")
        assert call_order == ["client"]
        dm.bonds.create_sales_order_draft.assert_not_called()

        # 3. Full two-step confirmation submits final shipping location & bond type
        call_order.clear()
        with patch.object(
            desk,
            "_prompt_order_client",
            side_effect=lambda *a, **k: (
                call_order.append("client"),
                {
                    "client_id": 5,
                    "client_name": "Meriem Ziani",
                    "client_phone": "0770889900",
                    "delivery_address": "Chéraga, Alger",
                },
            )[1],
        ), patch.object(
            desk,
            "_prompt_payment_confirmation",
            side_effect=lambda *a, **k: (
                call_order.append("payment"),
                {"bond_type": "BON_LIVRAISON", "delivery_address": "Dely Ibrahim, Alger"},
            )[1],
        ), patch.object(QMessageBox, "information"):
            desk.btn_livraison.click()

        assert call_order == ["client", "payment"]
        dm.bonds.create_sales_order_draft.assert_called_once()
        kw = dm.bonds.create_sales_order_draft.call_args.kwargs
        assert kw["bond_type"] == "BON_LIVRAISON"
        assert kw["delivery_address"] == "Dely Ibrahim, Alger"
    finally:
        desk.deleteLater()
