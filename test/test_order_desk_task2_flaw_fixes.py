# -*- coding: utf-8 -*-
"""
test/test_order_desk_task2_flaw_fixes.py
========================================
Automated Verification Suite for Task #2:
- Brand column (Col 0) expanded to 110px ensuring names like 'KBIOCHIMIE' are never truncated.
- Dedicated Price column (Col 6) set to 155px with crisp 1.5px border and no price clipping.
- Dedicated Action slot column (Col 7) expanded to 65px with framed slot (36x28px, 1.5px border)
  and borderless '+' button (32x24px), eliminating all clipping on bottom and right borders.
- Outer scroll area vertical scrollbar set to ScrollBarAlwaysOff so the bottom summary bar
  (catalog_bottom_bar) remains pinned and 100% visible, with internal table scrolling.
- Splitter safety bounds: catalog minimum 550px, cart minimum 320px, non-collapsible panels.
- Top filter bar: duplicate refresh button removed and clean spacing enforced.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication, QHeaderView
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
    ]
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "KBIOCHIMIE",
            "Product_Name": "ACCP ARC ALCOOL 500ML",
            "Category_Name": "HORMONOLOGIE ARC",
            "Color_Finish": "Standard",
            "Physical_Qty": 13,
            "Reserved_Qty": 1,
            "Available_Theoretical_Qty": 12,
            "Unit_Price_TTC": 16660.0,
            "Price_1_TTC": 16660.0,
            "Price_2_TTC": 15827.0,
            "Price_3_TTC": 14994.0,
            "Barcode": "4242005198030",
        },
        {
            "Product_ID": 102,
            "Brand_Mark": "ELECTROLUX",
            "Product_Name": "ACTIVATION ARC PACK",
            "Category_Name": "CONSOMABLE ARC",
            "Color_Finish": "Standard",
            "Physical_Qty": 74,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 74,
            "Unit_Price_TTC": 1190.0,
            "Price_1_TTC": 1190.0,
            "Price_2_TTC": 1130.0,
            "Price_3_TTC": 1071.0,
            "Barcode": "8806098321092",
        },
    ]
    return dm


def test_brand_column_anti_truncation_width(qapp, mock_data_manager):
    """Verifies that the Brand column has width >= 110px preventing ellipsis truncation."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    col0_width = desk.table.columnWidth(0)
    assert col0_width >= 110, f"Brand column width {col0_width}px is too narrow, expected >= 110px"

    item_mark = desk.table.item(0, 0)
    assert item_mark is not None
    assert item_mark.text() == "KBIOCHIMIE"


def test_action_column_and_slot_frame_proportions(qapp, mock_data_manager):
    """Verifies that Column 7 is wide enough and the AddActionSlot has crisp full borders."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # Column 7 width >= 60px
    col7_width = desk.table.columnWidth(7)
    assert col7_width >= 60, f"Column 7 width {col7_width}px expected >= 60px"

    action_widget = desk.table.cellWidget(0, 7)
    assert isinstance(action_widget, AddActionCellWidget)
    assert action_widget.slot_frame is not None

    # Frame geometry fits cleanly inside cell without edge clipping
    frame_w = action_widget.slot_frame.width()
    frame_h = action_widget.slot_frame.height()
    assert frame_w <= 38, f"Slot frame width {frame_w}px is too large"
    assert frame_h <= 30, f"Slot frame height {frame_h}px is too large"
    assert "border:" in action_widget.slot_frame.styleSheet()

    # Button inside frame has border: none and is enabled
    assert action_widget.btn_add.text() == "+"
    assert "border: none" in action_widget.btn_add.styleSheet()
    assert action_widget.btn_add.isEnabled() is True


def test_price_column_proportions_and_border(qapp, mock_data_manager):
    """Verifies that Column 6 is >= 150px and ProductPriceWidget has clean padding."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    col6_width = desk.table.columnWidth(6)
    assert col6_width >= 150, f"Price column width {col6_width}px expected >= 150px"

    price_widget = desk.table.cellWidget(0, 6)
    assert isinstance(price_widget, ProductPriceWidget)
    assert price_widget.btn_price.height() <= 30
    assert "16 660" in price_widget.btn_price.text()


def test_bottom_bar_pinned_and_outer_scroll_always_off(qapp, mock_data_manager):
    """Verifies that outer scroll area vertical scrollbar is ScrollBarAlwaysOff and bottom bar is pinned."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.resize(1180, 742)
    desk.show()
    qapp.processEvents()

    assert desk.scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert desk.catalog_bottom_bar.isVisible() is True
    assert desk.catalog_bottom_bar.height() == 38


def test_splitter_safe_minimum_bounds_and_non_collapsible(qapp, mock_data_manager):
    """Verifies that splitter prevents panels from collapsing."""
    # Clear any dirty settings for a pristine test
    settings = QSettings("StockLam", "OrderDesk")
    settings.remove("main_splitter_sizes")
    settings.remove("main_splitter_state")

    desk = OrderDeskWidget(data_manager=mock_data_manager)
    assert desk.catalog_panel.minimumWidth() >= 500
    assert desk.cart_panel.minimumWidth() >= 320
    assert desk.splitter.isCollapsible(0) is False
    assert desk.splitter.isCollapsible(1) is False
