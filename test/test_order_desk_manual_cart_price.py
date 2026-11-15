# -*- coding: utf-8 -*-
"""
test/test_order_desk_manual_cart_price.py
=========================================
Tests for Task #2 (Bureaux -> 1. Commandes):
- Manual inline editing of unit selling price (`Prix U.`) directly inside the Panier (`cart_table`).
- Instant validation preventing any selling price lower than the product's actual purchase price.
- Live line total (`Total TTC`) & grand total (`lbl_total`) recalculation on valid price/qty edits.
- Rejection + revert on invalid commit (`< purchase_price`, <= 0, non-numeric) + backend guard.
"""

import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QMessageBox

from database.bond_lifecycle_manager import BondLifecycleManager
from database.serial_tracking_manager import SerialTrackingManager
from ui.widgets.appliance_desks.order_desk_view import (
    CartPriceEditor,
    CartQtyStepper,
    CartRemoveCellWidget,
    OrderDeskWidget,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_mock_dm(purchase_price: float = 80000.0, selling_price: float = 100000.0):
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Client Comptoir", "Phone": "0550000000", "Price_Tier": "Prix_1"}
    ]
    dm.manufacturers.get_all_manufacturers.return_value = []
    dm.families.get_all_families.return_value = []
    dm.colors.get_all_colors.return_value = []
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "Réfrigérateur NoFrost",
            "Primary_Ref": "KGN39VLEB",
            "Category_Name": "Froid",
            "Color_Finish": "Inox",
            "Physical_Qty": 5,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 5,
            "Purchase_Price_TTC": purchase_price,
            "Unit_Price_TTC": selling_price,
            "Price_1_TTC": selling_price,
            "Price_2_TTC": 95000.0,
            "Price_3_TTC": 90000.0,
            "Barcode": "6130000001011",
        }
    ]
    dm.bonds.create_sales_order_draft.return_value = {
        "success": True,
        "order_id": 501,
        "order_number": "1-BC-TEST-501",
        "bond_type": "BON_C",
        "total_ttc": 190000.0,
    }
    return dm


def test_cart_manual_price_edit_and_instant_margin_validation(qapp):
    dm = _make_mock_dm(purchase_price=80000.0, selling_price=100000.0)
    desk = OrderDeskWidget(data_manager=dm)
    try:
        desk.refresh_catalog()
        prod = desk._catalog_filtered_items[0]
        desk._add_product_to_session(desk._active_session_id, prod)
        desk._add_product_to_session(desk._active_session_id, prod)  # qty = 2

        assert desk.cart_table.columnCount() == 6
        assert desk.cart_table.horizontalHeaderItem(3).text() == "Prix U."
        assert desk.cart_table.horizontalHeaderItem(4).text() == "Total TTC"
        assert isinstance(desk.cart_table.cellWidget(0, 2), CartQtyStepper)
        price_editor = desk.cart_table.cellWidget(0, 3)
        assert isinstance(price_editor, CartPriceEditor)
        assert isinstance(desk.cart_table.cellWidget(0, 5), CartRemoveCellWidget)
        assert price_editor.inp_price.text() == "100000"
        assert desk.lbl_cart_price_error.isHidden()

        # 1) Invalid typing (< purchase price 80000) shows instant inline error & keeps old price
        price_editor.inp_price.setText("75000")
        assert not desk.lbl_cart_price_error.isHidden()
        assert "80" in desk.lbl_cart_price_error.text()
        assert "#DC2626" in price_editor.inp_price.styleSheet().upper() or "#dc2626" in price_editor.inp_price.styleSheet()
        assert desk._sessions[desk._active_session_id]["cart"][0]["unit_price_ttc"] == 100000.0

        # 2) Valid price (95000 >= 80000) clears error and recalculates line + cart total live
        assert price_editor.try_commit_price("95000") is True
        assert desk.lbl_cart_price_error.isHidden()
        assert desk._sessions[desk._active_session_id]["cart"][0]["unit_price_ttc"] == 95000.0
        assert "190" in desk.cart_table.item(0, 4).text()
        assert "190" in desk.lbl_total.text()

        # 3) Committing lower price (< 80000) or 0 is rejected and reverted cleanly to 95000
        assert price_editor.try_commit_price("70000") is False
        assert price_editor.inp_price.text() == "95000"
        assert desk._sessions[desk._active_session_id]["cart"][0]["unit_price_ttc"] == 95000.0
        assert not desk.lbl_cart_price_error.isHidden()

        assert price_editor.try_commit_price("0") is False
        assert price_editor.inp_price.text() == "95000"

        # 4) Exact break-even price equal to purchase price (80000) IS allowed
        assert price_editor.try_commit_price("80000") is True
        assert desk.lbl_cart_price_error.isHidden()
        assert desk._sessions[desk._active_session_id]["cart"][0]["unit_price_ttc"] == 80000.0
        assert "160" in desk.lbl_total.text()

        # 5) Submitting submits edited valid price
        with patch.object(
            desk,
            "_prompt_order_client",
            return_value={
                "client_id": 1,
                "client_name": "Client Comptoir",
                "client_phone": "",
                "delivery_address": "",
            },
        ):
            with patch.object(QMessageBox, "information"):
                desk._submit_order("BON_C")
        dm.bonds.create_sales_order_draft.assert_called_once()
        submitted_items = dm.bonds.create_sales_order_draft.call_args.kwargs["items"]
        assert submitted_items[0]["unit_price_ttc"] == 80000.0
        assert submitted_items[0]["purchase_price"] == 80000.0
    finally:
        desk.deleteLater()


def test_submit_blocks_price_below_purchase_price(qapp):
    dm = _make_mock_dm(purchase_price=80000.0, selling_price=100000.0)
    desk = OrderDeskWidget(data_manager=dm)
    try:
        desk.refresh_catalog()
        prod = desk._catalog_filtered_items[0]
        desk._add_product_to_session(desk._active_session_id, prod)

        # 1) Uncommitted lower price typed directly into the editor blocks submission
        price_editor = desk.cart_table.cellWidget(0, 3)
        price_editor.inp_price.setText("60000")
        with patch.object(QMessageBox, "warning") as mock_warn, patch.object(QMessageBox, "information"):
            desk._submit_order("BON_C")
        assert mock_warn.called
        dm.bonds.create_sales_order_draft.assert_not_called()

        # 2) Direct cart payload defense-in-depth check also blocks inconsistent cart values
        desk._sessions[desk._active_session_id]["cart"][0]["unit_price_ttc"] = 60000.0
        desk.cart_table.removeCellWidget(0, 3)
        with patch.object(QMessageBox, "warning") as mock_warn2, patch.object(QMessageBox, "information"):
            desk._submit_order("BON_C")
        assert mock_warn2.called
        dm.bonds.create_sales_order_draft.assert_not_called()
    finally:
        desk.deleteLater()


def test_backend_rejects_selling_price_below_purchase_price():
    fake_cursor = MagicMock()
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor
    fake_db = MagicMock()

    @contextmanager
    def _ctx():
        yield fake_conn

    fake_db.get_db_connection = _ctx
    mgr = BondLifecycleManager(fake_db)

    with pytest.raises(ValueError):
        mgr.create_sales_order_draft(
            client_id=1,
            order_desk_user_id=1,
            items=[{"product_id": 101, "quantity": 1, "unit_price_ttc": 75000.0, "purchase_price": 80000.0}],
        )


def test_serial_tracking_catalog_exposes_purchase_price_ttc():
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = [
        {
            "Product_ID": 101,
            "Product_Name": "TV 55",
            "Brand_Mark": "LG",
            "Category_Name": "TV",
            "Color_Finish": "Noir",
            "Barcode": "123",
            "Primary_Ref": "OLED55",
            "All_Refs": "OLED55",
            "Physical_Qty": 3,
            "Reserved_Qty": 0,
            "Batch_Selling_Price_HT": 100000.0,
            "Batch_Selling_Price_HT_2": 95000.0,
            "Batch_Selling_Price_HT_3": 90000.0,
            "Default_Selling_Price_HT": 100000.0,
            "Selling_TVA_Percent": 0.0,
            "Max_Purchase_Price_TTC": 72500.0,
        }
    ]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor
    fake_db = MagicMock()

    @contextmanager
    def _ctx():
        yield fake_conn

    fake_db.get_db_connection = _ctx
    mgr = SerialTrackingManager(fake_db)
    rows = mgr.get_catalog_with_theoretical_stock(only_available=True)
    assert len(rows) == 1
    assert rows[0]["Purchase_Price_TTC"] == 72500.0
