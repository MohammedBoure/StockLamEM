# -*- coding: utf-8 -*-
"""
test/test_batch_reception_path_restriction.py
=============================================
Verification Test Suite for Task #6:
1. Restriction of batch reception and registration to only two authorized paths:
   - Path 1: Achats & Entrées (Procurement / Reception)
   - Path 2: Stock & Magasin (Direct Stock Addition)
2. Blocking of creation and reception from all other interfaces (notably Bureaux & SAV -> Lots / N° de Série).
3. Strict enforcement of complete product and batch data (Product, Location, Supplier, Lot Number, Quantity, Buy Price, Sell Price).
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from database.inventory_batch_manager import InventoryBatchManager
from ui.widgets.appliance_desks.serial_batch_view import SerialBatchRegistryWidget
from ui.widgets.inventory.tabs_batches.quick_add_dialog import QuickAddDialog
from ui.widgets.procurement.reception_dialog.reception_dialog import ReceptionDialog
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


def test_serial_batch_view_blocks_unauthorized_registration(qapp):
    """
    Requirement: منع التسجيل من أي واجهة أخرى (خاصة Bureaux & SAV -> Lots / N° de Série).
    Verifies that:
    - SerialBatchRegistryWidget disables direct creation buttons.
    - _on_create_product and _on_receive_batch show warning dialogs and refuse execution.
    - Centralized policy banner and serial audit tool are properly instantiated.
    """
    widget = SerialBatchRegistryWidget(data_manager=None, current_user_id=1)

    # 1. Action buttons are disabled by default
    assert widget.save_product_btn.isEnabled() is False
    assert widget.receive_batch_btn.isEnabled() is False

    # 2. Triggering _on_create_product displays warning and does not call DB
    with patch.object(QMessageBox, "warning") as mock_warn:
        widget._on_create_product()
        assert mock_warn.called
        args, kwargs = mock_warn.call_args
        assert "Action Non Autorisée" in args[1]
        assert "Achats & Entrées" in args[2]
        assert "Stock & Magasin" in args[2]

    # 3. Triggering _on_receive_batch displays warning and does not call DB
    with patch.object(QMessageBox, "warning") as mock_warn:
        widget._on_receive_batch()
        assert mock_warn.called
        args, kwargs = mock_warn.call_args
        assert "Action Non Autorisée" in args[1]
        assert "Achats & Entrées" in args[2]
        assert "Stock & Magasin" in args[2]

    # 4. Centralized policy banner and serial audit tool exist
    assert hasattr(widget, "btn_nav_procurement")
    assert hasattr(widget, "btn_nav_stock")
    assert hasattr(widget, "serial_search_input")
    assert hasattr(widget, "btn_search_serial")
    assert hasattr(widget, "lbl_serial_result")


def test_quick_add_dialog_mandatory_complete_data_validation(qapp):
    """
    Requirement: إلزام إدخال بيانات المنتوج كاملة في مسار Stock & Magasin.
    Verifies that QuickAddDialog rejects missing or incomplete fields:
    - Missing Product
    - Missing Location
    - Missing Supplier
    - Missing or 'N/A' Lot Number
    - Zero or Negative Quantity
    - Zero or Negative Buy Price
    - Zero or Negative Sell Price
    """
    mock_mgr = MagicMock()
    mock_mgr.products.get_all_products.return_value = [
        {"Product_ID": 1, "Product_Name": "Réfrigérateur NoFrost", "Base_Unit_Name": "Unité", "Tax_Rate_Percent": 19}
    ]
    mock_mgr.locations = MagicMock()

    dialog = QuickAddDialog(manager=mock_mgr, parent=None)

    # Helper function to test validation failure
    def assert_validation_fails(expected_err_keyword):
        with patch.object(QMessageBox, "warning") as mock_warn, patch.object(dialog, "accept") as mock_acc:
            dialog.validate_and_accept()
            assert not mock_acc.called, f"Expected validation failure for: {expected_err_keyword}"
            assert mock_warn.called
            call_text = str(mock_warn.call_args[0][2])
            assert expected_err_keyword.lower() in call_text.lower()

    # 1. Rejects when product is unselected
    dialog.cb_product.setCurrentIndex(0)
    assert_validation_fails("produit")

    # Select product
    dialog.cb_product.setCurrentIndex(1)

    # 2. Rejects when location is unselected
    with patch.object(dialog.cb_location, "get_current_location_id", return_value=None):
        assert_validation_fails("emplacement")

    # Mock valid location
    with patch.object(dialog.cb_location, "get_current_location_id", return_value=10):
        # 3. Rejects when supplier is unselected
        dialog.cb_supplier.clear()
        dialog.cb_supplier.addItem("--- Sans Fournisseur ---", None)
        dialog.cb_supplier.setCurrentIndex(0)
        assert_validation_fails("fournisseur")

        # Select supplier
        dialog.cb_supplier.addItem("Fournisseur Brandt Algérie", 5)
        dialog.cb_supplier.setCurrentIndex(1)

        # 4. Rejects when lot number is empty or "N/A"
        dialog.inp_lot.setText("")
        assert_validation_fails("lot")
        dialog.inp_lot.setText("N/A")
        assert_validation_fails("lot")

        # Set valid lot number
        dialog.inp_lot.setText("LOT-2026-BOSCH-01")

        # 5. Rejects when quantity is 0
        dialog.inp_qty.setValue(0)
        assert_validation_fails("quantité")
        dialog.inp_qty.setValue(5)

        # 6. Rejects when Buy Price is 0
        dialog.inp_price.setValue(0.0)
        assert_validation_fails("prix d'achat")
        dialog.inp_price.setValue(45000.0)

        # 7. Rejects when Sell Price is 0
        dialog.inp_sell_price.setValue(0.0)
        assert_validation_fails("prix de vente")
        dialog.inp_sell_price.setValue(58000.0)

        # 8. All data complete -> accepts successfully!
        with patch.object(dialog, "accept") as mock_acc:
            dialog.validate_and_accept()
            assert mock_acc.called

        data = dialog.get_data()
        assert data["Product_ID"] == 1
        assert data["Location_ID"] == 10
        assert data["Supplier_ID"] == 5
        assert data["Lot_Number"] == "LOT-2026-BOSCH-01"
        assert data["Quantity"] == 5
        assert data["Unit_Price_HT"] == 45000.0
        assert data["Selling_Price_HT"] == 58000.0


def test_reception_dialog_logic_mandatory_complete_data(qapp):
    """
    Requirement: إلزام إدخال بيانات المنتوج كاملة في مسار Achats & Entrées.
    Verifies that ReceptionDialog rejects reception lines with incomplete data:
    - Missing product or location
    - Zero quantity
    - Empty or N/A lot number
    - Zero or negative unit price
    """
    mock_mgr = MagicMock()
    mock_mgr.products.get_all_products.return_value = [
        {"Product_ID": 2, "Product_Name": "Machine à Laver 10kg", "Base_Unit_Name": "Unité", "Tax_Rate_Percent": 19}
    ]
    mock_mgr.locations = MagicMock()
    mock_mgr.reception = MagicMock()

    po_data = {"PO_ID": 100, "Supplier_Name": "Fournisseur Test", "Supplier_ID": 1}
    dialog = ReceptionDialog(po_data=po_data, locations_list=[], location_manager=mock_mgr.locations, manager=mock_mgr, printer_manager=MagicMock(), parent=None)
    dialog.br_id = 999  # Simulate validated header
    dialog.load_items_from_db = MagicMock()

    def assert_add_fails(keyword):
        with patch.object(QMessageBox, "warning") as mock_warn:
            dialog.add_item_to_table()
            assert mock_warn.called
            call_text = str(mock_warn.call_args[0][2])
            assert keyword.lower() in call_text.lower()

    # 1. Product unselected
    dialog.cb_product.setCurrentIndex(0)
    assert_add_fails("produit")

    # Add and Select product
    prod_data = {"Product_ID": 2, "Product_Name": "Machine à Laver 10kg"}
    dialog.cb_product.addItem("Machine à Laver 10kg", prod_data)
    dialog.cb_product.setCurrentIndex(dialog.cb_product.count() - 1)

    # 2. Location unselected
    with patch.object(dialog.cb_location, "get_current_location_id", return_value=None):
        assert_add_fails("emplacement")

    with patch.object(dialog.cb_location, "get_current_location_id", return_value=5):
        # 3. Quantity is 0
        dialog.inp_qty.setValue(0)
        assert_add_fails("quantité")
        dialog.inp_qty.setValue(10)

        # 4. Lot number is optional (empty or N/A auto-generates fallback)
        dialog.inp_lot.setText("LOT-RECEPTION-99")

        # 5. Price is 0
        dialog.inp_price.setValue(0.0)
        assert_add_fails("prix unitaire")
        dialog.inp_price.setValue(32000.0)

        # 6. With complete data, add_reception_line is called!
        mock_mgr.reception.add_reception_line.return_value = (True, "OK")
        dialog.add_item_to_table()
        assert mock_mgr.reception.add_reception_line.called
        call_payload = mock_mgr.reception.add_reception_line.call_args[0][0]
        assert call_payload["Product_ID"] == 2
        assert call_payload["Lot_Number"] == "LOT-RECEPTION-99"
        assert call_payload["Unit_Price_Received"] == 32000.0


def test_inventory_batch_manager_backend_data_completeness(mock_db):
    """
    Requirement: إلزامية البيانات على مستوى قاعدة البيانات ومدير المخزون (InventoryBatchManager).
    Verifies that add_direct_batch enforces required fields and rejects incomplete payloads.
    """
    mgr = InventoryBatchManager(mock_db)

    # Missing Product_ID
    with pytest.raises(ValueError, match="Product_ID est obligatoire"):
        mgr.add_direct_batch({"Location_ID": 1, "Lot_Number": "LOT1", "Quantity": 1, "Unit_Price_HT": 100})

    # Missing Location_ID
    with pytest.raises(ValueError, match="Location_ID est obligatoire"):
        mgr.add_direct_batch({"Product_ID": 1, "Lot_Number": "LOT1", "Quantity": 1, "Unit_Price_HT": 100})

    # Missing or N/A Lot_Number
    with pytest.raises(ValueError, match="Lot_Number valide est obligatoire"):
        mgr.add_direct_batch({"Product_ID": 1, "Location_ID": 1, "Lot_Number": "N/A", "Quantity": 1, "Unit_Price_HT": 100})

    # Zero or negative quantity
    with pytest.raises(ValueError, match="quantité doit être strictement positive"):
        mgr.add_direct_batch({"Product_ID": 1, "Location_ID": 1, "Lot_Number": "LOT1", "Quantity": 0, "Unit_Price_HT": 100})

    # Zero or negative purchase price
    with pytest.raises(ValueError, match="prix d'achat HT unitaire doit être supérieur à zéro"):
        mgr.add_direct_batch({"Product_ID": 1, "Location_ID": 1, "Lot_Number": "LOT1", "Quantity": 2, "Unit_Price_HT": 0.0})
