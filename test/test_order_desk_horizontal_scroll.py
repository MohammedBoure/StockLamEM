# -*- coding: utf-8 -*-
"""
test/test_order_desk_horizontal_scroll.py
=========================================
Automated Test Suite for Task #2:
- Catalog table 'Désignation Produit' column never clips or squishes when table is narrowed.
- Clamped minimum width >= 280px for Product Designation.
- Automatic smooth horizontal scrollbar activation (ScrollBarAsNeeded, ScrollPerPixel) on narrow widths.
- Dynamic expansion when space is available on wide displays.
- Splitter movement and header manual resize protection against clipping.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QHeaderView
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
        {"Client_ID": 1, "Client_Name": "Client Standard", "Phone": "0550000000"}
    ]
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "KGN39VLEB Combi NoFrost 368L Ultra Silence Inox",
            "Category_Name": "Gros Électroménager",
            "Color_Finish": "Inox",
            "Physical_Qty": 12,
            "Reserved_Qty": 2,
            "Available_Theoretical_Qty": 10,
            "Unit_Price_TTC": 115000.0,
            "Barcode": "4242005198030",
        },
        {
            "Product_ID": 102,
            "Brand_Mark": "Samsung",
            "Product_Name": "WW90T554DAN QuickDrive Ecobubble 9kg 1400tr",
            "Category_Name": "Lave-linge",
            "Color_Finish": "Gris Anthracite",
            "Physical_Qty": 6,
            "Reserved_Qty": 1,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 92000.0,
            "Barcode": "8806098321092",
        },
    ]
    return dm


def test_catalog_column_metrics_and_scroll_modes(qapp, mock_data_manager):
    """Verifies that catalog table uses ScrollPerPixel and has minimum 280px for designation."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # Verify scroll modes
    assert desk.table.horizontalScrollMode() == QAbstractItemView.ScrollPerPixel
    assert desk.table.verticalScrollMode() == QAbstractItemView.ScrollPerPixel

    # Verify column 1 configuration
    col1_width = desk.table.columnWidth(1)
    assert col1_width >= 280, f"Column 1 width is {col1_width}px, expected >= 280px"

    # Verify header label
    header_lbl = desk.table.horizontalHeaderItem(1).text()
    assert "Désignation" in header_lbl


def test_catalog_narrow_width_activates_horizontal_scrollbar(qapp, mock_data_manager):
    """Verifies that narrowing the catalog table never squishes designation and activates horizontal scrollbar."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # Simulate narrowing table to 600px (e.g. cart enlarged by splitter)
    desk.table.resize(600, 400)
    qapp.processEvents()
    desk._adjust_catalog_column_widths()

    # Column 1 must stay at least 280px
    col1_width = desk.table.columnWidth(1)
    assert col1_width >= 280, f"On narrow table (600px), col 1 width fell to {col1_width}px, expected >= 280px"

    # Total header length should be at least 918px
    total_header_w = desk.table.horizontalHeader().length()
    assert total_header_w >= 918, f"Total header width is {total_header_w}px, expected >= 918px"

    # Horizontal scrollbar must be active
    h_bar = desk.table.horizontalScrollBar()
    assert h_bar.maximum() > 0, f"Horizontal scrollbar maximum should be > 0 on narrow table, got {h_bar.maximum()}"


def test_catalog_wide_width_stretches_designation(qapp, mock_data_manager):
    """Verifies that on wide screens, column 1 smoothly expands to fill available viewport space."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    desk.resize(1600, 900)
    desk.show()
    qapp.processEvents()
    desk._adjust_catalog_column_widths()

    col1_width = desk.table.columnWidth(1)
    # On 1600px width, column 1 should be significantly wider than 280px
    assert col1_width >= 280
    assert col1_width >= 400, f"On 1600px screen, col 1 width was expected to expand >= 400px, got {col1_width}px"


def test_catalog_header_section_resized_guard(qapp, mock_data_manager):
    """Verifies that manual attempts to shrink column 1 below 260px are clamped."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    # Try resizing column 1 to 100px
    desk.table.setColumnWidth(1, 100)
    desk._on_catalog_header_section_resized(1, 280, 100)

    # Clamped to minimum 260px
    assert desk.table.columnWidth(1) >= 260, f"Expected clamped width >= 260px, got {desk.table.columnWidth(1)}"
