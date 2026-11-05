# -*- coding: utf-8 -*-
"""
test/test_order_desk_price_dropdown_menu.py
============================================
Automated Test Suite for Task #7:
- Dedicated Price column (Column 6, 'Prix TTC') displays ONLY the first price (Prix 1 - Détail / Comptoir).
- Elimination of text clutter and overlapping secondary prices:
  * QTableWidgetItem has empty text (no underlying ghost text).
  * No secondary labels rendered over the cell.
- Interactive dropdown indicator and menu on click:
  * btn_price has chevron indicator ('▾').
  * Clicking displays dropdown menu (QMenu) with all 3 pricing tiers (Prix 1, Prix 2, Prix 3).
  * Selecting an alternative tier updates displayed price and adds product at the chosen tier.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu, QPushButton
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
        {"Client_ID": 1, "Client_Name": "Client Standard", "Phone": "0550000000", "Price_Tier": "Prix_1"},
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
    ]
    return dm


def test_price_column_shows_only_first_price_and_no_overlapping_text(qapp, mock_data_manager):
    """Verifies that Column 6 renders only the primary price in a single button, eliminating all overlapping text."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # 1. Underlying QTableWidgetItem text must be empty (prevents double background rendering)
    it_price = desk.table.item(0, 6)
    assert it_price is not None
    assert it_price.text() == "", "Underlying item text must be empty to eliminate background ghost text!"
    assert "100 000" in it_price.toolTip()

    # 2. Cell widget must be ProductPriceWidget
    price_w = desk.table.cellWidget(0, 6)
    assert isinstance(price_w, ProductPriceWidget)
    assert price_w.p1 == 100000.0
    assert price_w.p2 == 95000.0
    assert price_w.p3 == 90000.0

    # 3. Only the first price is visible on the interactive button
    assert hasattr(price_w, "btn_price")
    assert isinstance(price_w.btn_price, QPushButton)
    btn_text = price_w.btn_price.text()
    assert "100 000" in btn_text
    assert "▾" in btn_text  # Chevron indicator
    # Ensure secondary sub-tier label is not visible in the cell layout
    assert price_w.lbl_sub.isVisible() is False


def test_price_dropdown_menu_generation_and_tier_actions(qapp, mock_data_manager, monkeypatch):
    """Verifies that the dropdown menu lists all 3 tiers and can be triggered on demand."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    price_w = desk.table.cellWidget(0, 6)
    assert isinstance(price_w, ProductPriceWidget)

    # Mock QMenu.exec_ to verify menu is invoked on clicking btn_price
    exec_called = []
    actions_found = []

    def mock_exec_(menu_self, pos=None):
        exec_called.append(True)
        for act in menu_self.actions():
            actions_found.append(act.text())
        return None

    monkeypatch.setattr(QMenu, "exec_", mock_exec_)

    # Trigger click on price button (connects to _show_price_menu)
    price_w.btn_price.click()

    assert len(exec_called) == 1
    assert any("Prix 1 (Détail / Comptoir)" in a for a in actions_found)
    assert any("Prix 2 (Demi-Gros)" in a for a in actions_found)
    assert any("Prix 3 (Grossiste B2B)" in a for a in actions_found)


def test_price_tier_selection_updates_display_and_cart_unit_price(qapp, mock_data_manager):
    """Verifies that selecting an alternative tier (Prix 2 or Prix 3) updates display and cart addition."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    price_w = desk.table.cellWidget(0, 6)
    assert isinstance(price_w, ProductPriceWidget)

    # 1. Select Prix 2 (Demi-Gros: 95 000 DA)
    price_w._select_tier("Prix_2", 95000.0)
    assert price_w.selected_tier == "Prix_2"
    assert price_w.current_price == 95000.0
    assert "95 000" in price_w.btn_price.text()
    assert "[DG]" in price_w.btn_price.text()

    # 2. Add product to cart -> should use chosen Prix 2 (95 000 DA)
    act_w = desk.table.cellWidget(0, 7)
    assert isinstance(act_w, AddActionCellWidget)
    act_w.btn_add.click()

    cart = desk._sessions["SESSION_1"]["cart"]
    assert len(cart) == 1
    assert cart[0]["product_id"] == 101
    assert cart[0]["unit_price_ttc"] == 95000.0

    # 3. Select Prix 3 (Grossiste B2B: 90 000 DA) for a second session
    s2 = desk._create_new_session()
    desk._active_session_id = s2

    price_w._select_tier("Prix_3", 90000.0)
    assert price_w.selected_tier == "Prix_3"
    assert price_w.current_price == 90000.0
    assert "90 000" in price_w.btn_price.text()
    assert "[G]" in price_w.btn_price.text()

    act_w._trigger_add()
    cart_s2 = desk._sessions[s2]["cart"]
    assert len(cart_s2) == 1
    assert cart_s2[0]["unit_price_ttc"] == 90000.0
