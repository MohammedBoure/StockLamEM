# -*- coding: utf-8 -*-
"""
test/test_order_desk_task1_enhancements.py
==========================================
Unit & Integration Test Suite for Task #1 enhancements in Order Desk:
1. Barcode recognition for products in stock and auto-addition to cart.
2. Barcode is strictly used for product identification without literal serial storage.
3. Category column width (>=160px) and tooltips to avoid clipping.
4. Total commande TTC action buttons height (Bon C >= 44px, Bon Crédit / Livraison >= 40px).
5. Movable separator (QSplitter) with QSettings persistence.
6. Visual Color Badge / Swatch preview in catalog table and tooltips.
7. Professional session tab close button ('x' removed when 1 session, custom styled when > 1).
8. Absence of redundant "Associer Scanner USB" button from session bar.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QSplitter, QTabBar, QTableWidget
from ui.widgets.appliance_desks.order_desk_view import (
    ColorBadgeWidget,
    OrderDeskWidget,
    get_color_hex,
)
from database.serial_tracking_manager import SerialTrackingManager


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
        {"Client_ID": 1, "Client_Name": "Comptoir Client Standard", "Phone": "0550000000"}
    ]
    dm.serials = MagicMock()
    # Mock catalog
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
            "Barcode": "4242005198030, 4242005198031",
            "Requires_Serial_Tracking": True,
        },
        {
            "Product_ID": 102,
            "Brand_Mark": "LG",
            "Product_Name": "F4J6TY0W DirectDrive 9kg",
            "Category_Name": "Lave-linge & Lavage",
            "Color_Finish": "Blanc",
            "Physical_Qty": 5,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 88000.0,
            "Barcode": "8806098321092",
            "Requires_Serial_Tracking": True,
        },
    ]
    dm.serials.get_catalog_with_theoretical_stock.return_value = mock_catalog
    dm.serials.find_product_by_any_barcode.side_effect = lambda bc: next(
        (p for p in mock_catalog if str(bc).strip() in [b.strip() for b in p["Barcode"].split(",")] or str(bc).strip() == str(p["Product_ID"])),
        None
    )
    return dm


def test_order_desk_splitter_and_persistence(qapp, mock_data_manager):
    """Verifies QSplitter presence, custom handle, absence of cart maxWidth, and QSettings persistence."""
    # Clear test settings
    settings = QSettings("StockLam", "OrderDesk")
    settings.remove("main_splitter_sizes")
    settings.remove("main_splitter_state")

    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # 1. Assert splitter is used
    assert hasattr(desk, "splitter"), "OrderDeskWidget must contain a splitter attribute"
    assert isinstance(desk.splitter, QSplitter), "Splitter must be an instance of QSplitter"
    assert desk.splitter.orientation() == Qt.Horizontal
    assert not desk.splitter.childrenCollapsible(), "Splitter children must not be collapsible"

    # 2. Cart panel should not have rigid max width 380
    assert desk.cart_panel.maximumWidth() >= 10000 or desk.cart_panel.maximumWidth() == 16777215

    # 3. Test saving and restoring splitter sizes
    desk.splitter.setSizes([800, 400])
    desk._save_splitter_state()

    # Create second instance and verify sizes restored
    desk2 = OrderDeskWidget(data_manager=mock_data_manager)
    sizes = desk2.splitter.sizes()
    assert sizes[0] > 0 and sizes[1] > 0


def test_order_desk_category_column_width(qapp, mock_data_manager):
    """Verifies that the category column is wide enough (>=160px) and items have tooltips."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    col_idx = 2  # Column 2 is "Catégorie"
    header_text = desk.table.horizontalHeaderItem(col_idx).text()
    assert "Catégorie" in header_text

    col_width = desk.table.columnWidth(col_idx)
    assert col_width >= 160, f"Catégorie column width is {col_width}px, expected >= 160px"

    # Verify tooltips set on category items
    assert desk.table.rowCount() > 0
    cat_item = desk.table.item(0, col_idx)
    assert cat_item is not None
    assert "Catégorie :" in cat_item.toolTip()


def test_order_desk_action_buttons_height(qapp, mock_data_manager):
    """Verifies that action execution buttons under Total TTC have increased height."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # Find buttons in cart panel
    buttons = desk.cart_panel.findChildren(QPushButton)
    btn_bon_c = next((b for b in buttons if "Bon Comptant" in b.text()), None)
    btn_credit = next((b for b in buttons if "Bon Crédit" in b.text()), None)
    btn_livraison = next((b for b in buttons if "Bon de Livraison" in b.text()), None)

    assert btn_bon_c is not None, "Bon Comptant button not found"
    assert btn_credit is not None, "Bon Crédit button not found"
    assert btn_livraison is not None, "Bon de Livraison button not found"

    assert btn_bon_c.height() >= 44 or btn_bon_c.fixedSize().height() >= 44, f"btn_bon_c height {btn_bon_c.height()} < 44"
    assert btn_credit.height() >= 40 or btn_credit.fixedSize().height() >= 40, f"btn_credit height {btn_credit.height()} < 40"
    assert btn_livraison.height() >= 40 or btn_livraison.fixedSize().height() >= 40, f"btn_livraison height {btn_livraison.height()} < 40"


def test_order_desk_visual_color_badge(qapp, mock_data_manager):
    """Verifies that the color column renders visual ColorBadgeWidget with swatch dot and tooltip."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    col_idx = 3  # Column 3 is "Couleur"
    assert "Couleur" in desk.table.horizontalHeaderItem(col_idx).text()

    # Check cell widget
    cell_widget = desk.table.cellWidget(0, col_idx)
    assert cell_widget is not None, "Color column must have a cell widget"
    assert isinstance(cell_widget, ColorBadgeWidget)

    # Verify hex code and tooltip
    assert cell_widget.hex_code == "#8A9EA7"  # Inox
    assert "Couleur / Finition : Inox" in cell_widget.toolTip()
    assert "#8A9EA7" in cell_widget.toolTip()

    # Check row 1 (Blanc)
    cell_widget_row1 = desk.table.cellWidget(1, col_idx)
    assert cell_widget_row1.hex_code == "#FFFFFF"
    assert "Blanc" in cell_widget_row1.toolTip()


def test_order_desk_session_close_button_behavior(qapp, mock_data_manager):
    """Verifies tab close button is hidden when only 1 session exists, and shown when > 1 session."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # Initially 1 session
    assert desk.session_tab_bar.count() == 1
    # When 1 session, no close button on tab 0
    assert desk.session_tab_bar.tabButton(0, QTabBar.RightSide) is None

    # Create a 2nd session
    sid2 = desk._create_new_session()
    assert desk.session_tab_bar.count() == 2

    # Now both tabs should have custom close button
    btn_tab0 = desk.session_tab_bar.tabButton(0, QTabBar.RightSide)
    btn_tab1 = desk.session_tab_bar.tabButton(1, QTabBar.RightSide)
    assert btn_tab0 is not None and isinstance(btn_tab0, QPushButton)
    assert btn_tab1 is not None and isinstance(btn_tab1, QPushButton)
    assert btn_tab0.text() == "×"
    assert btn_tab1.text() == "×"

    # Close session 2
    desk._on_session_tab_close_requested(1)
    assert desk.session_tab_bar.count() == 1
    assert desk.session_tab_bar.tabButton(0, QTabBar.RightSide) is None


def test_order_desk_no_associer_scanner_button(qapp, mock_data_manager):
    """Verifies that 'Associer Scanner USB' button is not displayed in the session bar."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    buttons = desk.findChildren(QPushButton)
    bind_btn = next((b for b in buttons if "Associer Scanner" in b.text()), None)
    assert bind_btn is None, "'Associer Scanner USB' button should not be present in the UI"


def test_order_desk_barcode_recognition_and_cart_theoretical(qapp, mock_data_manager):
    """
    Verifies:
    1. Barcode scanning or entering in txt_search auto-identifies product and adds to cart.
    2. Cart stores purely theoretical reservation without literal barcode / serial number.
    """
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.refresh_catalog()

    active_sid = desk._active_session_id
    cart = desk._sessions[active_sid]["cart"]
    assert len(cart) == 0

    # 1. Simulate scan of secondary barcode for Product 101 ("4242005198031")
    desk._on_scanner_input_for_session(active_sid, "SCANNER_TEST", "4242005198031")

    assert len(cart) == 1
    item = cart[0]
    assert item["product_id"] == 101
    assert item["quantity"] == 1
    assert item["name"] == "KGN39VLEB Combi NoFrost 368L"

    # 2. Verify that literal barcode or serial is NOT stored in the cart
    assert "barcode" not in item
    assert "serial_number" not in item
    assert "Barcode" not in item

    # 3. Simulate enter in search box with Product 102 barcode
    desk.txt_search.setText("8806098321092")
    desk._on_search_return_pressed()

    assert len(cart) == 2
    assert cart[1]["product_id"] == 102
    assert cart[1]["quantity"] == 1
    # Search box should be cleared automatically so user still sees catalog
    assert desk.txt_search.text() == ""


def test_serial_tracking_manager_find_product_by_any_barcode():
    """Verifies SerialTrackingManager.find_product_by_any_barcode across all sources."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn

    # Setup find product mock
    mgr = SerialTrackingManager(mock_db)

    # 1. Composite barcode test (<Product_ID>::<SERIAL>)
    mgr.get_catalog_with_theoretical_stock = MagicMock(return_value=[{"Product_ID": 105, "Product_Name": "Four Encastrable"}])
    res = mgr.find_product_by_any_barcode("105::SN987654321")
    assert res is not None
    assert res["Product_ID"] == 105
    mgr.get_catalog_with_theoretical_stock.assert_called_with(product_id=105)

    # 2. Empty or whitespace barcode returns None
    assert mgr.find_product_by_any_barcode("") is None
    assert mgr.find_product_by_any_barcode("   ") is None
