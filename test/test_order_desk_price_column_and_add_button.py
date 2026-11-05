# -*- coding: utf-8 -*-
"""
test/test_order_desk_price_column_and_add_button.py
===================================================
Automated Test Suite for Task #4:
- 8-Column layout in the Order Desk catalog table.
- Dedicated Price column (Column 6, 'Prix TTC') displaying all 3 pricing tiers:
  * Prix 1 (Détail / Comptoir)
  * Prix 2 (Demi-Gros / Revendeur)
  * Prix 3 (Grossiste B2B)
- Dedicated Action slot column (Column 7, 'Ajout') with borderless '+' button:
  * No border around the button itself.
  * Centered inside a framed cell slot with hover highlight.
  * Clicking '+' or the slot adds the product to the active session cart.
  * Out-of-stock products cleanly disabled ('—') with no vertical clipping.
- Automated client pricing tier resolution (Prix 1 / Prix 2 / Prix 3).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton
from ui.widgets.appliance_desks.order_desk_view import (
    AddActionCellWidget,
    OrderDeskWidget,
    ProductPriceWidget,
)


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
        {"Client_ID": 1, "Client_Name": "Client Comptoir (Standard)", "Phone": "0550000000", "Price_Tier": "Prix_1"},
        {"Client_ID": 2, "Client_Name": "Revendeur Demi-Gros", "Phone": "0660000000", "Price_Tier": "Prix_2"},
        {"Client_ID": 3, "Client_Name": "Grossiste B2B Pro", "Phone": "0770000000", "Price_Tier": "Prix_3"},
    ]
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "KGN39VLEB Combi NoFrost 368L",
            "Category_Name": "Réfrigérateurs",
            "Color_Finish": "Inox",
            "Physical_Qty": 10,
            "Reserved_Qty": 2,
            "Available_Theoretical_Qty": 8,
            "Unit_Price_TTC": 100000.0,
            "Price_1_TTC": 100000.0,
            "Price_2_TTC": 95000.0,
            "Price_3_TTC": 90000.0,
            "Barcode": "4242005198030",
        },
        {
            "Product_ID": 102,
            "Brand_Mark": "LG",
            "Product_Name": "F4J6TY0W DirectDrive 9kg",
            "Category_Name": "Lave-linge",
            "Color_Finish": "Blanc",
            "Physical_Qty": 0,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 0,  # Out of stock
            "Unit_Price_TTC": 80000.0,
            "Price_1_TTC": 80000.0,
            "Price_2_TTC": 76000.0,
            "Price_3_TTC": 72000.0,
            "Barcode": "8806098321092",
        },
    ]
    return dm


def test_catalog_table_eight_columns_and_headers(qapp, mock_data_manager):
    """Verifies that the table has exactly 8 columns with dedicated Price and Action headers."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    assert desk.table.columnCount() == 8

    headers = [desk.table.horizontalHeaderItem(i).text() for i in range(8)]
    assert headers[0] == "Marque"
    assert "Désignation" in headers[1]
    assert headers[2] == "Catégorie"
    assert headers[3] == "Couleur"
    assert headers[4] == "Phys."
    assert headers[5] == "Dispo."
    assert headers[6] == "Prix TTC"
    assert headers[7] == "Ajout"


def test_dedicated_price_column_three_tiers(qapp, mock_data_manager):
    """Verifies that Column 6 renders all 3 prices (Détail, Demi-Gros, Gros) cleanly."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    price_widget = desk.table.cellWidget(0, 6)
    assert isinstance(price_widget, ProductPriceWidget)
    assert "100 000" in price_widget.lbl_p1.text()
    assert "95 000" in price_widget.lbl_sub.text()
    assert "90 000" in price_widget.lbl_sub.text()

    # Verify detailed tooltip contains all 3 tiers
    tt = price_widget.toolTip()
    assert "Prix 1" in tt and "100 000" in tt
    assert "Prix 2" in tt and "95 000" in tt
    assert "Prix 3" in tt and "90 000" in tt


def test_action_column_borderless_plus_in_framed_slot(qapp, mock_data_manager):
    """Verifies that Column 7 renders only a '+' button with no border, inside a framed slot."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # 1. In stock row (Row 0)
    act_w0 = desk.table.cellWidget(0, 7)
    assert isinstance(act_w0, AddActionCellWidget)
    assert act_w0.is_available is True

    # Button has text '+' and no border
    btn0 = act_w0.btn_add
    assert btn0.text() == "+"
    assert btn0.isEnabled() is True
    assert "border: none" in btn0.styleSheet()

    # Framed slot container exists
    assert act_w0.slot_frame is not None
    assert "border:" in act_w0.slot_frame.styleSheet()

    # Click button -> adds to cart
    btn0.click()
    cart = desk._sessions["SESSION_1"]["cart"]
    assert len(cart) == 1
    assert cart[0]["product_id"] == 101
    assert cart[0]["unit_price_ttc"] == 100000.0  # Standard Prix 1 for client 1

    # 2. Out of stock row (Row 1)
    act_w1 = desk.table.cellWidget(1, 7)
    assert isinstance(act_w1, AddActionCellWidget)
    assert act_w1.is_available is False
    btn1 = act_w1.btn_add
    assert btn1.text() == "—"
    assert btn1.isEnabled() is False


def test_client_price_tier_automatic_application(qapp, mock_data_manager):
    """Verifies that selecting a wholesale client automatically applies Prix 2 or Prix 3 when adding to cart."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # Associate Client 2 (Prix 2 - Demi-Gros) to SESSION_1
    desk._sessions["SESSION_1"]["client_id"] = 2
    act_w0 = desk.table.cellWidget(0, 7)
    act_w0.btn_add.click()

    cart = desk._sessions["SESSION_1"]["cart"]
    assert len(cart) == 1
    assert cart[0]["unit_price_ttc"] == 95000.0  # Demi-Gros price applied!

    # Create new session for Client 3 (Prix 3 - Gros)
    s2 = desk._create_new_session()
    desk._sessions[s2]["client_id"] = 3
    desk._active_session_id = s2

    act_w0._trigger_add()
    cart_s2 = desk._sessions[s2]["cart"]
    assert len(cart_s2) == 1
    assert cart_s2[0]["unit_price_ttc"] == 90000.0  # Grossiste B2B price applied!


def test_zero_vertical_clipping_metrics(qapp, mock_data_manager):
    """Verifies that button and slot metrics comfortably fit within row height eliminating any clipping."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    row_h = desk.table.verticalHeader().defaultSectionSize()
    assert row_h >= 44, f"Row height {row_h}px should be at least 44px"

    act_w = desk.table.cellWidget(0, 7)
    slot_h = act_w.slot_frame.height()
    assert slot_h <= 34, f"Slot frame height {slot_h}px exceeds 34px"
    assert slot_h < row_h - 10, "Slot frame must leave comfortable margins to prevent clipping"
