# -*- coding: utf-8 -*-
"""
test/test_quick_add_color_assignment.py
======================================
Automated test suite verifying Task #4:
In Stock & Magasin -> Stock Actuel -> Ajout Rapide (QuickAddDialog):
- Selection and assignment of newly added product color finishes (Product_Colors / Color_Finish)
- Dynamic color swatch preview indicator and color dropdown
- Automatic pre-selection based on product Master Data or existing batch data
- Persistence of Color_Finish on Products_Master in direct batch creation and editing
"""

import sys
from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from ui.widgets.inventory.tabs_batches.quick_add_dialog import QuickAddDialog
from database.inventory_batch_manager import InventoryBatchManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_inventory_manager():
    mgr = MagicMock()
    mgr.locations.get_all_locations.return_value = [
        {"Location_ID": 1, "Location_Name": "Dépôt Central", "Parent_ID": None, "Allow_POS_Sales": True}
    ]
    mgr.locations.get_all_locations_tree.return_value = [
        {"Location_ID": 1, "Location_Name": "Dépôt Central", "Parent_ID": None, "children": []}
    ]

    prod1 = {
        "Product_ID": 101,
        "Product_Name": "Réfrigérateur Combiné NoFrost 450L",
        "Manuf_Name": "Brandt",
        "Manuf_Cat_No": "BFC-450X",
        "Color_Finish": "Inox",
        "Base_Unit_Name": "Pièce",
        "Tax_Rate_Percent": 19.0,
        "Selling_TVA_Percent": 19.0,
        "Default_Selling_Price_HT": 85000.0,
    }
    prod2 = {
        "Product_ID": 102,
        "Product_Name": "Lave-linge Frontal 10.5kg",
        "Manuf_Name": "LG",
        "Manuf_Cat_No": "F4V5VYP0W",
        "Color_Finish": "Blanc",
        "Base_Unit_Name": "Pièce",
        "Tax_Rate_Percent": 19.0,
        "Selling_TVA_Percent": 19.0,
        "Default_Selling_Price_HT": 92000.0,
    }
    prod3 = {
        "Product_ID": 103,
        "Product_Name": "Four Encastrable 60cm",
        "Manuf_Name": "Samsung",
        "Manuf_Cat_No": "NV70K",
        "Color_Finish": "",
        "Base_Unit_Name": "Pièce",
        "Tax_Rate_Percent": 19.0,
        "Selling_TVA_Percent": 19.0,
        "Default_Selling_Price_HT": 65000.0,
    }

    mgr.products.get_all_products.return_value = [prod1, prod2, prod3]
    mgr.colors.get_all_colors.return_value = [
        {"Color_ID": 1, "Color_Name": "Inox", "Color_Code": "#8A9EA7", "Is_Active": 1},
        {"Color_ID": 2, "Color_Name": "Blanc", "Color_Code": "#FFFFFF", "Is_Active": 1},
        {"Color_ID": 3, "Color_Name": "Noir", "Color_Code": "#1E293B", "Is_Active": 1},
        {"Color_ID": 4, "Color_Name": "Silver", "Color_Code": "#CBD5E1", "Is_Active": 1},
    ]

    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {"Supplier_ID": 10, "Supplier_Name": "Fournisseur Général Électro"}
    ]
    mock_conn.cursor.return_value = mock_cursor
    mock_db.get_raw_connection.return_value = mock_conn
    mgr.db = mock_db

    return mgr


def test_quick_add_dialog_color_widgets_initialization(qapp, mock_inventory_manager):
    """Verifies QuickAddDialog contains color combo and visual swatch badge."""
    dlg = QuickAddDialog(mock_inventory_manager, parent=None)

    assert hasattr(dlg, "cb_color")
    assert hasattr(dlg, "lbl_color_swatch")
    assert dlg.cb_color.count() >= 5  # "--- Non définie / Standard ---" + 4 colors

    # First item is standard / non définie
    assert "---" in dlg.cb_color.itemText(0)

    # All registered colors present
    combo_texts = [dlg.cb_color.itemText(i) for i in range(dlg.cb_color.count())]
    assert "Inox" in combo_texts
    assert "Blanc" in combo_texts
    assert "Noir" in combo_texts
    assert "Silver" in combo_texts


def test_quick_add_dialog_product_selection_auto_color(qapp, mock_inventory_manager):
    """Verifies that selecting a product automatically pre-fills its Color_Finish and updates swatch."""
    dlg = QuickAddDialog(mock_inventory_manager, parent=None)

    # Select Product 1 (Inox)
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 101:
            dlg.cb_product.setCurrentIndex(i)
            break

    assert dlg.cb_color.currentText() == "Inox"
    assert "#8A9EA7" in dlg.lbl_color_swatch.styleSheet()

    # Select Product 2 (Blanc)
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 102:
            dlg.cb_product.setCurrentIndex(i)
            break

    assert dlg.cb_color.currentText() == "Blanc"
    assert "#FFFFFF" in dlg.lbl_color_swatch.styleSheet()

    # Select Product 3 (No Color)
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 103:
            dlg.cb_product.setCurrentIndex(i)
            break

    assert dlg.cb_color.currentIndex() == 0 or dlg.cb_color.currentText().startswith("---")


def test_quick_add_dialog_custom_color_assignment_and_get_data(qapp, mock_inventory_manager):
    """Verifies that user can select or type custom color and get_data returns Color_Finish."""
    dlg = QuickAddDialog(mock_inventory_manager, parent=None)

    # Select Product 1
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 101:
            dlg.cb_product.setCurrentIndex(i)
            break

    # Override color with "Noir"
    dlg.set_selected_color("Noir")
    assert dlg.cb_color.currentText() == "Noir"
    assert "#1E293B" in dlg.lbl_color_swatch.styleSheet()

    # Fill minimum required fields
    dlg.inp_lot.setText("LOT-2026-X1")
    dlg.inp_qty.setValue(5)
    dlg.inp_price.setValue(50000.0)
    dlg.inp_sell_price.setValue(85000.0)
    dlg.cb_supplier.setCurrentIndex(1)

    data = dlg.get_data()
    assert data["Product_ID"] == 101
    assert data["Color_Finish"] == "Noir"
    assert data["Quantity"] == 5
    assert data["Lot_Number"] == "LOT-2026-X1"


def test_quick_add_dialog_prefill_from_batch_data(qapp, mock_inventory_manager):
    """Verifies that QuickAddDialog pre-fills color when editing an existing batch."""
    batch_data = {
        "Batch_ID": 55,
        "Product_ID": 102,
        "Location_ID": 1,
        "Supplier_ID": 10,
        "Quantity_Initial": 10,
        "Lot_Number": "LOT-EDIT-01",
        "Color_Finish": "Silver",
        "Unit_Price_Received": 60000.0,
        "Selling_Price_HT": 92000.0,
    }

    dlg = QuickAddDialog(mock_inventory_manager, parent=None, batch_data=batch_data)
    assert dlg.cb_color.currentText() == "Silver"
    assert "#CBD5E1" in dlg.lbl_color_swatch.styleSheet()

    data = dlg.get_data()
    assert data["Color_Finish"] == "Silver"


def test_inventory_batch_manager_color_finish_persistence():
    """Verifies add_direct_batch and update_direct_batch update Products_Master.Color_Finish."""
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_db.get_raw_connection.return_value = mock_conn
    mock_cursor.lastrowid = 777

    mgr = InventoryBatchManager(mock_db)

    # 1. Test add_direct_batch
    data_add = {
        "Product_ID": 101,
        "Location_ID": 1,
        "Lot_Number": "LOT-COLOR-01",
        "Expiry_Date": "2028-12-31",
        "Quantity": 12,
        "Unit_Price_HT": 45000.0,
        "Selling_Price_HT": 70000.0,
        "Color_Finish": "Gris Anthracite",
        "Supplier_ID": 5,
    }

    success = mgr.add_direct_batch(data_add, user_id=1)
    assert success is True

    # Check SQL executed for Products_Master update
    executed_sqls = [call[0][0] for call in mock_cursor.execute.call_args_list]
    color_update_calls = [
        sql for sql in executed_sqls
        if "UPDATE Products_Master SET Color_Finish" in sql
    ]
    assert len(color_update_calls) >= 1

    # Check Color_Finish argument
    for call in mock_cursor.execute.call_args_list:
        if "UPDATE Products_Master SET Color_Finish" in call[0][0]:
            assert call[0][1] == ("Gris Anthracite", 101)

    # 2. Test update_direct_batch
    mock_cursor.reset_mock()
    mock_cursor.fetchone.return_value = (None,)  # BR_ID is NULL

    data_upd = {
        "Product_ID": 101,
        "Location_ID": 1,
        "Lot_Number": "LOT-COLOR-01",
        "Expiry_Date": "2028-12-31",
        "Quantity": 15,
        "Unit_Price_HT": 45000.0,
        "Selling_Price_HT": 70000.0,
        "Color_Finish": "Inox",
        "Supplier_ID": 5,
    }

    success_upd = mgr.update_direct_batch(777, data_upd, user_id=1)
    assert success_upd is True

    # Check Color_Finish updated on Products_Master
    executed_sqls_upd = [call[0][0] for call in mock_cursor.execute.call_args_list]
    color_upd_calls = [
        sql for sql in executed_sqls_upd
        if "UPDATE Products_Master SET Color_Finish" in sql
    ]
    assert len(color_upd_calls) >= 1

    for call in mock_cursor.execute.call_args_list:
        if "UPDATE Products_Master SET Color_Finish" in call[0][0]:
            assert call[0][1] == ("Inox", 101)
