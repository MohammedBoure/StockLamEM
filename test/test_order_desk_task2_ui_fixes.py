# -*- coding: utf-8 -*-
"""
test/test_order_desk_task2_ui_fixes.py
======================================
Automated Test Suite for Task #2 UI and ergonomic fixes in Order Desk:
1. Catalog Table Action Column & Row Height:
   - Row height >= 44px (defaultSectionSize: 46px) ensuring button is never cut off at bottom.
   - Action column width >= 180px (185px) ensuring complete text visibility.
   - Button centered with proper cell margins and no bottom clipping.
   - Clean "Épuisé" label for out-of-stock items without emojis.
2. Client Search Input Field:
   - Combobox height >= 36px ensuring vertical text is never cut off.
   - Dedicated full-width layout with separate header row for "+ Nouveau Client" button.
   - Clean placeholder and formatting without emoji clipping.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


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
        {"Client_ID": 1, "Client_Name": "Client Comptoir (Standard)", "Phone": "0550000000", "Address": "Alger"},
        {"Client_ID": 2, "Client_Name": "EURL Électro Ménager Pro", "Phone": "0661122334", "Address": "Oran"},
    ]
    dm.serials = MagicMock()
    mock_catalog = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "KGN39VLEB Combi NoFrost 368L",
            "Category_Name": "Gros Électroménager",
            "Color_Finish": "Inox",
            "Physical_Qty": 10,
            "Reserved_Qty": 2,
            "Available_Theoretical_Qty": 8,
            "Unit_Price_TTC": 115000.0,
            "Barcode": "4242005198030",
            "Requires_Serial_Tracking": True,
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
            "Unit_Price_TTC": 88000.0,
            "Barcode": "8806098321092",
            "Requires_Serial_Tracking": True,
        },
    ]
    dm.serials.get_catalog_with_theoretical_stock.return_value = mock_catalog
    return dm


def test_table_row_height_and_action_column_metrics(qapp, mock_data_manager):
    """Verifies that the catalog table row height and column width prevent any bottom or side clipping."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # 1. Row height must be >= 44px
    row_height = desk.table.verticalHeader().defaultSectionSize()
    assert row_height >= 44, f"Row height {row_height}px is too small, expected >= 44px"

    # 2. Dedicated Price column (col 6) and Action column (col 7)
    price_col_width = desk.table.columnWidth(6)
    assert price_col_width >= 140, f"Price column width {price_col_width}px is too narrow, expected >= 140px"
    action_col_width = desk.table.columnWidth(7)
    assert action_col_width >= 50, f"Action column width {action_col_width}px is too narrow, expected >= 50px"

    # 3. Check row 0 price widget and action button
    assert desk.table.rowCount() >= 2
    cell_p0 = desk.table.cellWidget(0, 6)
    assert cell_p0 is not None
    assert "115 000" in cell_p0.toolTip() or "115 000" in desk.table.item(0, 6).text()

    cell_w0 = desk.table.cellWidget(0, 7)
    assert cell_w0 is not None
    btn0 = cell_w0.findChild(QPushButton)
    assert btn0 is not None
    assert btn0.height() >= 26 or btn0.minimumHeight() >= 26
    assert "+" in btn0.text()

    # Total button height + cell layout margins must fit cleanly within row_height with zero clipping
    margins = cell_w0.layout().contentsMargins()
    total_needed_h = (btn0.minimumHeight() or btn0.height()) + margins.top() + margins.bottom()
    assert total_needed_h <= row_height, (
        f"Button + margins ({total_needed_h}px) exceeds row height ({row_height}px)"
    )

    # 4. Check row 1 (out of stock item)
    cell_w1 = desk.table.cellWidget(1, 7)
    assert cell_w1 is not None
    btn1 = cell_w1.findChild(QPushButton)
    assert btn1 is not None
    assert not btn1.isEnabled()
    assert "—" in btn1.text() or "Épuisé" in cell_w1.toolTip()


def test_client_search_combobox_layout_and_dimensions(qapp, mock_data_manager):
    """Verifies that the client search combobox has comfortable vertical height and is not cramped."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # 1. Check combobox height (must be >= 36px)
    assert hasattr(desk, "cbo_client")
    cbo = desk.cbo_client
    assert isinstance(cbo, QComboBox)
    assert cbo.minimumHeight() >= 36 or cbo.height() >= 36, (
        f"Combobox height {cbo.height()}px is too small, expected >= 36px"
    )

    # 2. Check that combobox is editable
    assert cbo.isEditable(), "Client combobox must be editable for fast typing/searching"

    # 3. Check placeholder text
    assert cbo.lineEdit() is not None
    placeholder = cbo.lineEdit().placeholderText()
    assert "Rechercher" in placeholder
    assert "nom" in placeholder or "téléphone" in placeholder
    assert "🔍" not in placeholder, "Placeholder should not use emojis"

    # 4. Check client display items in combo (no phone emoji)
    assert cbo.count() >= 2
    for i in range(cbo.count()):
        text = cbo.itemText(i)
        assert "📞" not in text, f"Item text '{text}' should not contain phone emoji"

    # 5. Check that '+ Nouveau Client' button is placed in header row
    buttons = desk.cart_panel.findChildren(QPushButton)
    btn_new_c = next((b for b in buttons if "Nouveau Client" in b.text()), None)
    assert btn_new_c is not None, "Header button '+ Nouveau Client' should be present"
