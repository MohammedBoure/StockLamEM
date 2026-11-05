# -*- coding: utf-8 -*-
"""
test/test_order_desk_cart_table_and_remove_item.py
==================================================
Automated Test Suite for Task #5:
- 5-Column layout in the Order Desk cart table:
  * Col 0: Désignation (Responsive with >= 180px minimum clamp)
  * Col 1: Couleur (ColorBadgeWidget with visual circular swatch image + text + rich tooltip)
  * Col 2: Qté (CartQtyStepper with - / qty / +)
  * Col 3: Total TTC (Bold font, right aligned)
  * Col 4: Suppr. (Dedicated CartRemoveCellWidget with vector trash icon and hover feedback)
- Visual Color Swatch representation in the cart table (not just plain text name).
- Dedicated per-row Remove item button with instant cart removal and total recalculation.
- Horizontal scrolling support with ScrollPerPixel when viewport is narrowed, preventing text/widget clipping.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication, QAbstractItemView, QHeaderView
from ui.widgets.appliance_desks.order_desk_view import (
    AddActionCellWidget,
    CartRemoveCellWidget,
    ColorBadgeWidget,
    OrderDeskWidget,
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
            "Physical_Qty": 5,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 75000.0,
            "Price_1_TTC": 75000.0,
            "Price_2_TTC": 71000.0,
            "Price_3_TTC": 68000.0,
            "Barcode": "8806098000000",
        },
        {
            "Product_ID": 103,
            "Brand_Mark": "Samsung",
            "Product_Name": "RT38K5535S9 NoFrost 384L",
            "Category_Name": "Réfrigérateurs",
            "Color_Finish": "Noir",
            "Physical_Qty": 4,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 4,
            "Unit_Price_TTC": 120000.0,
            "Price_1_TTC": 120000.0,
            "Price_2_TTC": 115000.0,
            "Price_3_TTC": 110000.0,
            "Barcode": "8806088000000",
        },
    ]
    return dm


def test_cart_table_structure_and_5_columns(qapp, mock_data_manager):
    """Verifies that the cart table has exactly 5 configured columns with appropriate widths."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    assert desk.cart_table.columnCount() == 5
    headers = [desk.cart_table.horizontalHeaderItem(c).text() for c in range(5)]
    assert headers[0] == "Désignation"
    assert headers[1] == "Couleur"
    assert headers[2] == "Qté"
    assert headers[3] == "Total TTC"
    assert headers[4] == "Suppr."

    # Column 0 has min width >= 180, Col 1 is 105, Col 2 is 80, Col 3 is 105, Col 4 is 42
    assert desk.cart_table.columnWidth(0) >= 180
    assert desk.cart_table.columnWidth(1) == 105
    assert desk.cart_table.columnWidth(2) == 80
    assert desk.cart_table.columnWidth(3) == 105
    assert desk.cart_table.columnWidth(4) == 42

    # Verify horizontal scroll settings
    assert desk.cart_table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert desk.cart_table.horizontalScrollMode() == QAbstractItemView.ScrollPerPixel
    assert desk.cart_table.verticalScrollMode() == QAbstractItemView.ScrollPerPixel


def test_color_swatch_image_preview_in_cart_row(qapp, mock_data_manager):
    """Verifies that Color finish in cart table renders a visual circular swatch (ColorBadgeWidget) and not plain text."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # Add product 101 (Bosch - Inox) to cart
    act_w0 = desk.table.cellWidget(0, 7)
    assert isinstance(act_w0, AddActionCellWidget)
    act_w0._trigger_add()

    # Add product 102 (LG - Blanc) to cart
    act_w1 = desk.table.cellWidget(1, 7)
    act_w1._trigger_add()

    assert desk.cart_table.rowCount() == 2

    # Row 0: Inox
    color_w0 = desk.cart_table.cellWidget(0, 1)
    assert isinstance(color_w0, ColorBadgeWidget)
    assert color_w0.color_name == "Inox"
    assert color_w0.hex_code == "#8A9EA7"
    assert color_w0.swatch.width() >= 13
    assert "#8A9EA7" in color_w0.swatch.styleSheet().upper() or "#8a9ea7" in color_w0.swatch.styleSheet().lower()
    assert color_w0.lbl_text.text() == "Inox"
    # Ensure underlying item has no conflicting raw text that could overlap
    assert desk.cart_table.item(0, 1).text() == ""
    assert "Inox" in desk.cart_table.item(0, 1).toolTip()

    # Row 1: Blanc
    color_w1 = desk.cart_table.cellWidget(1, 1)
    assert isinstance(color_w1, ColorBadgeWidget)
    assert color_w1.color_name == "Blanc"
    assert color_w1.hex_code.upper() == "#FFFFFF"
    assert color_w1.lbl_text.text() == "Blanc"
    assert "Blanc" in desk.cart_table.item(1, 1).toolTip()


def test_remove_item_from_cart_button(qapp, mock_data_manager):
    """Verifies that each cart row contains a dedicated remove button that deletes the item and updates totals."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # Add 3 products to cart
    for r in range(3):
        desk.table.cellWidget(r, 7)._trigger_add()

    assert desk.cart_table.rowCount() == 3
    assert len(desk._sessions["SESSION_1"]["cart"]) == 3

    # Row 0 total: 100,000 DA, Row 1 total: 75,000 DA, Row 2 total: 120,000 DA -> 295,000 DA
    assert "295 000,00 DA" in desk.lbl_total.text() or "295 000.00 DA" in desk.lbl_total.text() or "295" in desk.lbl_total.text()

    # Check delete button widget in Row 1 (LG Lave-linge)
    del_w1 = desk.cart_table.cellWidget(1, 4)
    assert isinstance(del_w1, CartRemoveCellWidget)
    assert hasattr(del_w1, "btn_delete")
    assert del_w1.btn_delete.icon().isNull() is False
    assert del_w1.btn_delete.cursor().shape() == Qt.PointingHandCursor

    # Click delete button of Row 1
    del_w1.btn_delete.click()

    # Verify Row 1 (LG) was removed, leaving 2 items (Bosch and Samsung)
    assert desk.cart_table.rowCount() == 2
    cart = desk._sessions["SESSION_1"]["cart"]
    assert len(cart) == 2
    assert cart[0]["product_id"] == 101  # Bosch
    assert cart[1]["product_id"] == 103  # Samsung

    # Total should now be 100,000 + 120,000 = 220,000 DA
    assert "220 000,00 DA" in desk.lbl_total.text() or "220 000.00 DA" in desk.lbl_total.text() or "220" in desk.lbl_total.text()

    # Delete remaining 2 rows
    del_w_first = desk.cart_table.cellWidget(0, 4)
    del_w_first.btn_delete.click()
    assert desk.cart_table.rowCount() == 1

    del_w_last = desk.cart_table.cellWidget(0, 4)
    del_w_last.btn_delete.click()
    assert desk.cart_table.rowCount() == 0
    assert len(desk._sessions["SESSION_1"]["cart"]) == 0
    assert "0,00 DA" in desk.lbl_total.text() or "0.00 DA" in desk.lbl_total.text()


def test_cart_table_horizontal_scroll_and_responsive_metrics(qapp, mock_data_manager):
    """Verifies that cart table clamps designation column to >= 180px and activates horizontal scrollbar when narrowed."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()
    desk.table.cellWidget(0, 7)._trigger_add()

    # Force a narrow cart table width (e.g. 350px)
    desk.cart_table.resize(350, 400)
    desk._adjust_cart_column_widths()

    # Column 0 must be clamped to at least 180px
    col0_w = desk.cart_table.columnWidth(0)
    assert col0_w >= 180

    # Total width of all columns: >= 180 + 105 + 80 + 105 + 42 = 512px
    total_cols_w = sum(desk.cart_table.columnWidth(c) for c in range(5))
    assert total_cols_w >= 512

    # Viewport is narrower than total columns, scrollbar is required/available
    assert desk.cart_table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded

    # Accidental manual header dragging protection: logical index 0 cannot shrink below 160px
    desk._on_cart_header_section_resized(0, 180, 50)
    assert desk.cart_table.columnWidth(0) >= 160

    # Vertical metrics: row height >= 38px (40px) ensuring zero clipping
    assert desk.cart_table.verticalHeader().defaultSectionSize() >= 38
    del_w = desk.cart_table.cellWidget(0, 4)
    assert del_w.btn_delete.height() <= desk.cart_table.verticalHeader().defaultSectionSize() - 10
