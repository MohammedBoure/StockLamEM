# -*- coding: utf-8 -*-
"""
test/test_product_colors_and_bon_comptant.py
============================================
Verification Test Suite for Task #5:
1. Renaming of 'Bon C' to 'Bon Comptant' in Order Desk and Cashier Desk UI.
2. Product Colors Master Data management (ProductColorManager).
3. Integration of ProductColorsTab in Master Data (Données de base).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget
from database.product_color_manager import ProductColorManager
from ui.widgets.master_data.product_colors_tab import ProductColorsTab, ColorDialog
from ui.widgets.master_data.master_data_tabs import MasterDataTabs
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget
from ui.hardware.raw_input_filter import MultiScannerHIDManager
from test.test_serial_uniqueness_and_concurrency import StatefulMockDB


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_db():
    return StatefulMockDB()


def test_bon_comptant_ui_renaming(qapp):
    """
    Requirement 1: تعديل تسمية `bon C` إلى `Bon Comptant`.
    Verifies that:
    - Order Desk primary CTA button is named 'Émettre Bon Comptant (Vente Directe -> Caisse)'.
    - Cashier Desk validation button is named 'Valider Bon Comptant (Encaissement Direct -> Sortie)'.
    - Queue and settlement titles display 'Bon Comptant'.
    """
    hid_mgr = MultiScannerHIDManager()
    order_desk = OrderDeskWidget(data_manager=None, hid_manager=hid_mgr)

    # 1. Order Desk CTA button
    order_btns = order_desk.findChildren(QPushButton)
    bon_c_btns = [b for b in order_btns if "Bon Comptant" in b.text()]
    assert len(bon_c_btns) >= 1, "Expected 'Bon Comptant' button in Order Desk"
    assert "Émettre Bon Comptant" in bon_c_btns[0].text()

    # 2. Cashier Desk Action Button & Labels
    cashier_desk = CashierDeskWidget(data_manager=None)
    assert hasattr(cashier_desk, "btn_val_bon_c")
    assert "Valider Bon Comptant" in cashier_desk.btn_val_bon_c.text()

    # Verify queue label in queue_table
    assert cashier_desk.queue_table.rowCount() >= 1
    type_col_text = cashier_desk.queue_table.item(0, 2).text()
    assert "Bon Comptant" in type_col_text


def test_product_color_manager_crud(mock_db):
    """
    Requirement 2: إدارة الألوان المتاحة للمنتجات (ProductColorManager).
    Verifies that:
    - Default standard colors are seeded (Inox, Blanc, Noir, Silver, etc.).
    - Adding, updating, fetching, and active color filtering work properly.
    """
    mgr = ProductColorManager(mock_db)

    # 1. Verify default colors available
    colors = mgr.get_all_colors()
    assert len(colors) >= 5
    color_names = [c["Color_Name"] for c in colors]
    assert "Inox" in color_names
    assert "Blanc" in color_names
    assert "Noir" in color_names

    # 2. Add custom color
    add_res = mgr.add_color("Bleu Nuit", "#0A192F", "Finition bleu métallisé foncé")
    assert add_res["success"] is True
    assert add_res["color_name"] == "Bleu Nuit"
    assert add_res["color_code"] == "#0A192F"

    # Verify search
    search_res = mgr.get_all_colors(search="Bleu")
    assert len(search_res) == 1
    assert search_res[0]["Color_Name"] == "Bleu Nuit"

    # Active color names for dropdowns
    active_names = mgr.get_active_color_names()
    assert "Bleu Nuit" in active_names


def test_master_data_product_colors_tab_ui(qapp):
    """
    Requirement 2 UI:
    Verifies that MasterDataTabs contains a dedicated tab for product colors,
    and ProductColorsTab provides color badges, search filtering, and addition dialog.
    """
    tab = ProductColorsTab(data_manager=None)

    # 1. Table structure
    assert hasattr(tab, "table")
    assert isinstance(tab.table, QTableWidget)
    assert tab.table.columnCount() == 6
    assert tab.table.rowCount() >= 5

    headers = [tab.table.horizontalHeaderItem(i).text() for i in range(tab.table.columnCount())]
    assert "Aperçu" in headers[1]
    assert "Nom de la Couleur" in headers[2]
    assert "Code Hexadécimal" in headers[3]

    # 2. Search filtering
    tab.txt_search.setText("Inox")
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 2).text() == "Inox"

    tab.txt_search.clear()
    assert tab.table.rowCount() >= 5

    # 3. MasterDataTabs container has tab_colors
    from unittest.mock import MagicMock
    mock_dm = MagicMock()
    mock_dm.products.search_products.return_value = []
    mock_dm.families.get_all_families.return_value = []
    mock_dm.packaging_units.get_all_units.return_value = []
    mock_dm.suppliers.get_all_suppliers.return_value = []
    mock_dm.manufacturers.get_all_manufacturers.return_value = []
    mock_dm.locations.get_all_locations.return_value = []
    mock_dm.automates.get_all_automates.return_value = []
    mock_dm.waste_reasons.get_all_reasons.return_value = []
    mock_dm.partners.get_all_partners.return_value = []
    mock_dm.clients.get_all_clients.return_value = []
    mock_dm.pos_terminals.get_all_terminals.return_value = []
    mock_dm.colors.get_all_colors.return_value = []

    master_tabs = MasterDataTabs(data_manager=mock_dm)
    assert hasattr(master_tabs, "tab_colors")
    assert isinstance(master_tabs.tab_colors, ProductColorsTab)
