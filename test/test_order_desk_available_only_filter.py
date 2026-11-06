# -*- coding: utf-8 -*-
"""
test/test_order_desk_available_only_filter.py
=============================================
Automated Test Suite for Task #6:
- Dedicated 'Disponibles uniquement' filter in OrderDeskWidget filter bar:
  * Enabled by default (isChecked() == True).
  * Automatically filters out exhausted / out-of-stock items (Available_Theoretical_Qty <= 0).
  * Unchecking reveals exhausted items with disabled '—' buttons.
  * Resetting filters restores the filter to checked (True) by default.
  * Integration with SerialTrackingManager.get_catalog_with_theoretical_stock(only_available=True).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox
from ui.widgets.appliance_desks.order_desk_view import (
    AddActionCellWidget,
    OrderDeskWidget,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_data_manager_mixed_stock():
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}
    dm.clients = MagicMock()
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Client Standard", "Phone": "0550000000", "Price_Tier": "Prix_1"},
    ]
    dm.serials = MagicMock()
    # 5 products: 3 available (101, 103, 105) and 2 exhausted (102, 104)
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "KGN39VLEB Combi NoFrost 368L",
            "Category_Name": "Réfrigérateurs",
            "Color_Finish": "Inox",
            "Physical_Qty": 10,
            "Reserved_Qty": 2,
            "Available_Theoretical_Qty": 8,  # Available
            "Unit_Price_TTC": 100000.0,
            "Price_1_TTC": 100000.0,
            "Price_2_TTC": 95000.0,
            "Price_3_TTC": 90000.0,
            "Barcode": "4242005198030",
        },
        {
            "Product_ID": 102,
            "Brand_Mark": "Samsung",
            "Product_Name": "WW90T554DAN QuickDrive 9kg",
            "Category_Name": "Lave-linge",
            "Color_Finish": "Blanc",
            "Physical_Qty": 2,
            "Reserved_Qty": 2,
            "Available_Theoretical_Qty": 0,  # Exhausted
            "Unit_Price_TTC": 85000.0,
            "Price_1_TTC": 85000.0,
            "Price_2_TTC": 80000.0,
            "Price_3_TTC": 78000.0,
            "Barcode": "8806098000000",
        },
        {
            "Product_ID": 103,
            "Brand_Mark": "LG",
            "Product_Name": "F4J6TY0W DirectDrive 9kg",
            "Category_Name": "Lave-linge",
            "Color_Finish": "Silver",
            "Physical_Qty": 6,
            "Reserved_Qty": 1,
            "Available_Theoretical_Qty": 5,  # Available
            "Unit_Price_TTC": 92000.0,
            "Price_1_TTC": 92000.0,
            "Price_2_TTC": 87000.0,
            "Price_3_TTC": 84000.0,
            "Barcode": "8806088000000",
        },
        {
            "Product_ID": 104,
            "Brand_Mark": "Brandt",
            "Product_Name": "BPI6449BL Induction 4 Foyers",
            "Category_Name": "Cuisson & Fours",
            "Color_Finish": "Noir",
            "Physical_Qty": 0,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 0,  # Exhausted
            "Unit_Price_TTC": 48000.0,
            "Price_1_TTC": 48000.0,
            "Price_2_TTC": 45000.0,
            "Price_3_TTC": 42000.0,
            "Barcode": "3660767963245",
        },
        {
            "Product_ID": 105,
            "Brand_Mark": "Midea",
            "Product_Name": "Inverter 12000 BTU Pro",
            "Category_Name": "Climatisation",
            "Color_Finish": "Blanc",
            "Physical_Qty": 7,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 7,  # Available
            "Unit_Price_TTC": 64000.0,
            "Price_1_TTC": 64000.0,
            "Price_2_TTC": 60000.0,
            "Price_3_TTC": 58000.0,
            "Barcode": "6939962711029",
        },
    ]
    return dm


def test_available_only_filter_initial_state_and_default(qapp, mock_data_manager_mixed_stock):
    """Verifies that the 'Disponibles uniquement' filter is created and active by default."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_mixed_stock)

    assert hasattr(desk, "chk_available_only")
    assert isinstance(desk.chk_available_only, QCheckBox)
    assert desk.chk_available_only.text() in ("En stock", "Disponibles uniquement")
    assert desk.chk_available_only.isChecked() is True
    assert desk.btn_available_only is desk.chk_available_only

    # Catalog initially shows strictly available products (3 out of 5)
    desk.refresh_catalog()
    assert desk.table.rowCount() == 3
    assert len(desk._catalog_filtered_items) == 3

    # Ensure all items in table have Available_Theoretical_Qty > 0
    loaded_ids = [it["Product_ID"] for it in desk._catalog_filtered_items]
    assert loaded_ids == [101, 103, 105]
    assert 102 not in loaded_ids
    assert 104 not in loaded_ids

    # KPI badge reflects only available products
    assert "3 produits trouvés" in desk.lbl_catalog_count_badge.text()


def test_toggling_available_only_filter_reveals_and_hides_exhausted_items(qapp, mock_data_manager_mixed_stock):
    """Verifies that unchecking the filter shows exhausted products, and checking it hides them immediately."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_mixed_stock)
    desk.refresh_catalog()

    # 1. Uncheck filter (False): All 5 products should appear
    desk.chk_available_only.setChecked(False)
    assert desk.table.rowCount() == 5
    assert len(desk._catalog_filtered_items) == 5
    assert "5 produits trouvés" in desk.lbl_catalog_count_badge.text()

    # Verify exhausted rows have disabled '—' buttons
    # Product 102 is at row 1, Product 104 is at row 3
    act_w1 = desk.table.cellWidget(1, 7)
    assert isinstance(act_w1, AddActionCellWidget)
    assert act_w1.is_available is False
    assert act_w1.btn_add.text() == "—"
    assert act_w1.btn_add.isEnabled() is False

    act_w3 = desk.table.cellWidget(3, 7)
    assert isinstance(act_w3, AddActionCellWidget)
    assert act_w3.is_available is False
    assert act_w3.btn_add.text() == "—"
    assert act_w3.btn_add.isEnabled() is False

    # 2. Check filter back (True): Only 3 available products remain
    desk.chk_available_only.setChecked(True)
    assert desk.table.rowCount() == 3
    assert len(desk._catalog_filtered_items) == 3
    loaded_ids = [it["Product_ID"] for it in desk._catalog_filtered_items]
    assert 102 not in loaded_ids
    assert 104 not in loaded_ids
    assert "3 produits trouvés" in desk.lbl_catalog_count_badge.text()


def test_reset_filters_restores_available_only_to_default_true(qapp, mock_data_manager_mixed_stock):
    """Verifies that clicking 'Réinitialiser' restores the 'Disponibles uniquement' filter to True."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_mixed_stock)
    desk.refresh_catalog()

    # User unchecks filter and modifies text search
    desk.chk_available_only.setChecked(False)
    desk.txt_search.setText("Bosch")
    assert desk.chk_available_only.isChecked() is False

    # Click reset filters
    desk._reset_filters()

    # Must be restored to True by default
    assert desk.chk_available_only.isChecked() is True
    assert desk.txt_search.text() == ""
    assert desk.table.rowCount() == 3


def test_backend_serial_tracking_manager_only_available_flag():
    """Verifies that SerialTrackingManager.get_catalog_with_theoretical_stock honors only_available flag."""
    from database.serial_tracking_manager import SerialTrackingManager

    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Return 2 database rows: 1 available (phys 5, res 1 -> avail 4) and 1 exhausted (phys 2, res 2 -> avail 0)
    mock_cursor.fetchall.return_value = [
        {
            "Product_ID": 1,
            "Product_Name": "Prod Dispo",
            "Brand_Mark": "Bosch",
            "Category_Name": "Froid",
            "Color_Finish": "Inox",
            "Barcode": "1111",
            "Warranty_Months": 24,
            "Requires_Serial_Tracking": True,
            "Default_Selling_Price_HT": 100.0,
            "Selling_TVA_Percent": 19.0,
            "Physical_Qty": 5,
            "Reserved_Qty": 1,
            "Batch_Selling_Price_HT": 100.0,
            "Batch_Selling_Price_HT_2": 95.0,
            "Batch_Selling_Price_HT_3": 90.0,
        },
        {
            "Product_ID": 2,
            "Product_Name": "Prod Épuisé",
            "Brand_Mark": "LG",
            "Category_Name": "Lavage",
            "Color_Finish": "Blanc",
            "Barcode": "2222",
            "Warranty_Months": 24,
            "Requires_Serial_Tracking": True,
            "Default_Selling_Price_HT": 80.0,
            "Selling_TVA_Percent": 19.0,
            "Physical_Qty": 2,
            "Reserved_Qty": 2,
            "Batch_Selling_Price_HT": 80.0,
            "Batch_Selling_Price_HT_2": 75.0,
            "Batch_Selling_Price_HT_3": 70.0,
        },
    ]

    mgr = SerialTrackingManager(mock_db)

    # 1. only_available=True -> returns only product 1
    res_only_avail = mgr.get_catalog_with_theoretical_stock(only_available=True)
    assert len(res_only_avail) == 1
    assert res_only_avail[0]["Product_ID"] == 1
    assert res_only_avail[0]["Available_Theoretical_Qty"] == 4

    # 2. only_available=False -> returns both products
    res_all = mgr.get_catalog_with_theoretical_stock(only_available=False)
    assert len(res_all) == 2
    assert res_all[1]["Product_ID"] == 2
    assert res_all[1]["Available_Theoretical_Qty"] == 0
