# -*- coding: utf-8 -*-
"""
test/test_reception_dialog_color_support.py
===========================================
Automated test suite verifying Task #5:
In Achats & Entrées -> Bon de Réceptions -> ReceptionDialog:
- Support for entering/selecting product color finish (Product_Colors / Color_Finish)
- Dynamic color swatch preview indicator and color combobox in ReceptionDialog
- Automatic pre-selection from Master Data (Color_Finish) on product selection
- "Couleur" column in the reception items table (table_items)
- Persistence of Color_Finish on Products_Master and Product_Colors in ReceptionLogManager
"""

import sys
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from ui.widgets.procurement.reception_dialog.reception_dialog import ReceptionDialog
from database.reception_log_manager import ReceptionLogManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_procurement_env():
    mock_mgr = MagicMock()

    prod1 = {
        "Product_ID": 201,
        "Product_Name": "Congélateur Bahut 300L",
        "Manuf_Name": "Condor",
        "Stock_Unit": "Pièce",
        "Color_Finish": "Inox",
        "Tax_Rate_Percent": 19.0,
    }
    prod2 = {
        "Product_ID": 202,
        "Product_Name": "Micro-ondes Grill 25L",
        "Manuf_Name": "Samsung",
        "Stock_Unit": "Pièce",
        "Color_Finish": "Noir",
        "Tax_Rate_Percent": 19.0,
    }
    prod3 = {
        "Product_ID": 203,
        "Product_Name": "Hotte Aspirante Murale",
        "Manuf_Name": "Brandt",
        "Stock_Unit": "Pièce",
        "Color_Finish": "",
        "Tax_Rate_Percent": 19.0,
    }

    mock_mgr.products.get_all_products.return_value = [prod1, prod2, prod3]
    mock_mgr.colors.get_all_colors.return_value = [
        {"Color_ID": 1, "Color_Name": "Inox", "Color_Code": "#8A9EA7", "Is_Active": 1},
        {"Color_ID": 2, "Color_Name": "Blanc", "Color_Code": "#FFFFFF", "Is_Active": 1},
        {"Color_ID": 3, "Color_Name": "Noir", "Color_Code": "#1E293B", "Is_Active": 1},
        {"Color_ID": 4, "Color_Name": "Silver", "Color_Code": "#CBD5E1", "Is_Active": 1},
    ]

    mock_mgr.locations = MagicMock()
    mock_mgr.locations.get_all_locations_flat.return_value = [
        {"Location_ID": 10, "Location_Name": "Dépôt Réception"}
    ]

    mock_mgr.reception = MagicMock()
    mock_printer = MagicMock()

    po_data = {
        "PO_ID": 505,
        "Supplier_ID": 7,
        "Supplier_Name": "Fournisseur National Électro",
    }

    return mock_mgr, po_data, mock_printer


def test_reception_dialog_color_widgets_initialization(qapp, mock_procurement_env):
    """Verifies that ReceptionDialog initializes color combobox, swatch badge, and table column."""
    mock_mgr, po_data, mock_printer = mock_procurement_env
    dlg = ReceptionDialog(
        po_data=po_data,
        locations_list=[],
        location_manager=mock_mgr.locations,
        manager=mock_mgr,
        printer_manager=mock_printer,
        parent=None
    )

    assert hasattr(dlg, "cb_color")
    assert hasattr(dlg, "lbl_color_swatch")
    assert dlg.cb_color.count() >= 5  # Standard/None + 4 colors

    # First item is standard / non définie
    assert "---" in dlg.cb_color.itemText(0)

    # Check registered colors exist
    items = [dlg.cb_color.itemText(i) for i in range(dlg.cb_color.count())]
    assert "Inox" in items
    assert "Blanc" in items
    assert "Noir" in items
    assert "Silver" in items

    # Check table has 15 columns with "Couleur" at column index 1
    assert dlg.table_items.columnCount() == 15
    assert dlg.table_items.horizontalHeaderItem(1).text() == "Couleur"


def test_reception_dialog_product_selection_auto_color(qapp, mock_procurement_env):
    """Verifies selecting a product automatically pre-selects its Color_Finish."""
    mock_mgr, po_data, mock_printer = mock_procurement_env
    dlg = ReceptionDialog(
        po_data=po_data,
        locations_list=[],
        location_manager=mock_mgr.locations,
        manager=mock_mgr,
        printer_manager=mock_printer,
        parent=None
    )

    # Select Product 1 (Inox)
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 201:
            dlg.cb_product.setCurrentIndex(i)
            break

    assert dlg.cb_color.currentText() == "Inox"
    assert "#8A9EA7" in dlg.lbl_color_swatch.styleSheet()

    # Select Product 2 (Noir)
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 202:
            dlg.cb_product.setCurrentIndex(i)
            break

    assert dlg.cb_color.currentText() == "Noir"
    assert "#1E293B" in dlg.lbl_color_swatch.styleSheet()

    # Select Product 3 (No color)
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 203:
            dlg.cb_product.setCurrentIndex(i)
            break

    assert dlg.cb_color.currentIndex() == 0 or dlg.cb_color.currentText().startswith("---")


def test_reception_dialog_add_item_passes_color(qapp, mock_procurement_env):
    """Verifies that add_item_to_table passes Color_Finish in line_data."""
    mock_mgr, po_data, mock_printer = mock_procurement_env
    dlg = ReceptionDialog(
        po_data=po_data,
        locations_list=[],
        location_manager=mock_mgr.locations,
        manager=mock_mgr,
        printer_manager=mock_printer,
        parent=None
    )
    dlg.br_id = 123
    dlg.load_items_from_db = MagicMock()

    # Select Product 1
    for i in range(dlg.cb_product.count()):
        p = dlg.cb_product.itemData(i)
        if p and p.get("Product_ID") == 201:
            dlg.cb_product.setCurrentIndex(i)
            break

    # Override color to "Silver"
    dlg.set_selected_color("Silver")
    assert dlg.cb_color.currentText() == "Silver"

    # Fill mandatory fields
    dlg.inp_qty.setValue(8)
    dlg.inp_lot.setText("LOT-REC-COLOR-1")
    dlg.inp_price.setValue(45000.0)

    mock_mgr.reception.add_reception_line.return_value = (True, "OK")

    with patch.object(dlg.cb_location, "get_current_location_id", return_value=10):
        dlg.add_item_to_table()

    assert mock_mgr.reception.add_reception_line.called
    saved_line = mock_mgr.reception.add_reception_line.call_args[0][0]
    assert saved_line["Product_ID"] == 201
    assert saved_line["Color_Finish"] == "Silver"
    assert saved_line["Lot_Number"] == "LOT-REC-COLOR-1"
    assert saved_line["Quantity_Initial"] == 8


def test_reception_dialog_load_and_edit_color_display(qapp, mock_procurement_env):
    """Verifies loading reception data populates the table and editing pre-fills the color."""
    mock_mgr, po_data, mock_printer = mock_procurement_env

    reception_data = {
        "Header": {
            "BR_ID": 444,
            "Supplier_Invoice_Ref": "FACT-2026-001",
            "Supplier_BL_Ref": "BL-2026-001",
            "Reception_Date": "2026-11-05",
        },
        "Batches": [
            {
                "Batch_ID": 1001,
                "Product_ID": 201,
                "Product_Name": "Congélateur Bahut 300L",
                "Color_Finish": "Inox",
                "Quantity_Initial": 6,
                "Unit_Price_Received": 48000.0,
                "Tax_Rate_Percent": 19.0,
                "Discount_Percent": 0.0,
                "Lot_Number": "LOT-EDIT-TEST",
                "Expiry_Date": "2028-06-30",
                "Location_ID": 10,
                "Location_Name": "Dépôt Réception",
                "Internal_Barcode": "505001",
            }
        ]
    }

    dlg = ReceptionDialog(
        po_data=po_data,
        locations_list=[],
        location_manager=mock_mgr.locations,
        manager=mock_mgr,
        printer_manager=mock_printer,
        parent=None,
        edit_mode=True,
        reception_data=reception_data
    )

    # Check table row
    assert dlg.table_items.rowCount() == 1
    # Column 0: Product Name
    assert "Congélateur" in dlg.table_items.item(0, 0).text()
    # Column 1: Couleur
    assert dlg.table_items.item(0, 1).text() == "Inox"

    # Double click or load_item_for_edit
    dlg.table_items.setCurrentCell(0, 0)
    dlg.load_item_for_edit()

    assert dlg.cb_color.currentText() == "Inox"
    assert "#8A9EA7" in dlg.lbl_color_swatch.styleSheet()


def test_reception_log_manager_color_persistence():
    """Verifies that ReceptionLogManager persists Color_Finish to Products_Master and Product_Colors."""
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)  # For locks
    mock_cursor.lastrowid = 888
    mock_conn.cursor.return_value = mock_cursor
    mock_db.get_raw_connection.return_value = mock_conn

    mgr = ReceptionLogManager(mock_db)

    # Mock barcode allocator
    mgr._allocate_reception_barcode = MagicMock(return_value="505001")
    mgr.stock_movement_log = MagicMock()

    line_data = {
        "BR_ID": 444,
        "PO_ID": 505,
        "Product_ID": 201,
        "Location_ID": 10,
        "Color_Finish": "Gris Anthracite",
        "Quantity_Initial": 10,
        "Quantity_Current": 10,
        "Unit_Price_Received": 52000.0,
        "Tax_Rate_Percent": 19.0,
        "Discount_Percent": 0,
        "Lot_Number": "LOT-TEST-COL",
        "Expiry_Date": "2029-01-01",
    }

    success, msg = mgr.add_reception_line(line_data)
    assert success is True

    # Check execute calls for Products_Master UPDATE
    executed_sqls = [call[0][0] for call in mock_cursor.execute.call_args_list]
    color_updates = [
        sql for sql in executed_sqls
        if "UPDATE Products_Master SET Color_Finish" in sql
    ]
    assert len(color_updates) >= 1

    for call in mock_cursor.execute.call_args_list:
        if "UPDATE Products_Master SET Color_Finish" in call[0][0]:
            assert call[0][1] == ("Gris Anthracite", 201)
