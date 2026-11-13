"""Tests for Bon de Réception Réf selector + '+' button and optional Lot across product entry."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.inventory_batch_manager import InventoryBatchManager
from ui.widgets.inventory.tabs_batches.quick_add_dialog import QuickAddDialog
from ui.widgets.procurement.reception_dialog import ReceptionDialog


def _get_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_mock_manager():
    mgr = MagicMock()
    mgr.products = MagicMock()
    mgr.products.get_all_products.return_value = [
        {
            "Product_ID": 10,
            "Product_Name": "Lave-linge 8KG",
            "Manuf_Name": "LG",
            "Primary_Ref": "REF-LG-8K",
            "All_Refs": "REF-LG-8K | REF-LG-ALT",
            "Stock_Unit": "Unité",
            "Base_Unit_Name": "Unité",
            "Default_Selling_Price_HT": 75000.0,
        }
    ]
    mgr.locations = MagicMock()
    mgr.locations.get_all_locations.return_value = [
        {"Location_ID": 1, "Location_Name": "Magasin Principal", "Parent_ID": None}
    ]
    mgr.locations.get_location_hierarchy.return_value = [
        {"Location_ID": 1, "Location_Name": "Magasin Principal", "Parent_ID": None}
    ]
    mgr.colors = MagicMock()
    mgr.colors.get_all_colors.return_value = []

    refs_store = {
        10: [
            {"Ref_ID": 1, "Product_ID": 10, "Ref_Code": "REF-LG-8K", "Is_Primary": True},
            {"Ref_ID": 2, "Product_ID": 10, "Ref_Code": "REF-LG-ALT", "Is_Primary": False},
        ]
    }

    def _get_refs(pid):
        return list(refs_store.get(pid, []))

    def _add_ref(pid, code):
        code = str(code).strip()
        refs_store.setdefault(pid, []).append(
            {"Ref_ID": 88, "Product_ID": pid, "Ref_Code": code, "Is_Primary": False}
        )
        return 88

    mgr.product_refs = MagicMock()
    mgr.product_refs.get_references_for_product.side_effect = _get_refs
    mgr.product_refs.add_reference.side_effect = _add_ref

    mgr.reception = MagicMock()
    mgr.reception.add_reception_line.return_value = (True, "OK")
    mgr.reception.get_reception_full_details.return_value = {
        "Header": {"BR_ID": 7, "Supplier_ID": 1, "Supplier_Name": "Fournisseur Test"},
        "Batches": [
            {
                "Batch_ID": 70,
                "Product_ID": 10,
                "Product_Name": "Lave-linge 8KG",
                "Location_ID": 1,
                "Location_Name": "Magasin Principal",
                "Quantity_Initial": 2,
                "Unit_Price_Received": 55000.0,
                "Tax_Rate_Percent": 0.0,
                "Discount_Percent": 0.0,
                "Lot_Number": "LOT-AUTO",
                "Ref_Code": "REF-LG-NEW",
                "Internal_Barcode": "1000000000018",
                "Stock_Unit": "Unité",
            }
        ],
    }

    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    conn.cursor.return_value = cursor
    mgr.db = MagicMock()
    mgr.db.get_raw_connection.return_value = conn
    return mgr


class TestReceptionRefAndOptionalLot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _get_qapp()

    def test_reception_dialog_ref_dropdown_plus_button_and_persistence(self):
        mgr = _make_mock_manager()
        dlg = ReceptionDialog(
            {"PO_ID": None},
            mgr.locations.get_all_locations(),
            mgr.locations,
            mgr,
            MagicMock(),
        )
        dlg.br_id = 7
        dlg.toggle_inputs_state(True)

        self.assertFalse(dlg.cb_ref.isEnabled())
        self.assertFalse(dlg.btn_add_ref.isEnabled())

        # Select product 10
        dlg.cb_product.setCurrentIndex(1)
        self.assertTrue(dlg.cb_ref.isEnabled())
        self.assertTrue(dlg.btn_add_ref.isEnabled())
        self.assertEqual(dlg.cb_ref.count(), 2)

        # Click '+' to add a new Réf directly in Bon de Réception
        with patch(
            "ui.widgets.procurement.reception_dialog.reception_dialog_logic.QInputDialog.getText",
            return_value=("REF-LG-NEW", True),
        ):
            dlg.btn_add_ref.click()

        mgr.product_refs.add_reference.assert_called_once_with(10, "REF-LG-NEW")
        self.assertEqual(dlg.cb_ref.currentData(), "REF-LG-NEW")

        # Leave Lot empty (optional), add item
        dlg.cb_location.select_location_id(1)
        dlg.inp_qty.setValue(2)
        dlg.inp_price.setValue(55000.0)
        dlg.inp_lot.setText("")

        dlg.add_item_to_table()
        mgr.reception.add_reception_line.assert_called_once()
        line_data = mgr.reception.add_reception_line.call_args[0][0]
        self.assertEqual(line_data["Ref_Code"], "REF-LG-NEW")
        self.assertTrue(line_data["Lot_Number"].startswith("LOT-"))
        dlg.close()

    def test_quick_add_and_batch_manager_allow_empty_lot(self):
        mgr = _make_mock_manager()
        dlg = QuickAddDialog(mgr)
        dlg.cb_product.setCurrentIndex(1)
        dlg.cb_location.select_location_id(1)
        dlg.cb_supplier.addItem("Fournisseur 1", 1)
        dlg.cb_supplier.setCurrentIndex(1)
        dlg.inp_qty.setValue(3)
        dlg.inp_price.setValue(10000.0)
        dlg.inp_sell_price.setValue(12000.0)
        dlg.inp_lot.setText("")  # Optional!

        with patch.object(dlg, "accept") as mock_accept:
            dlg.validate_and_accept()
            self.assertTrue(mock_accept.called)

        payload = dlg.get_data()
        self.assertTrue(payload["Lot_Number"].startswith("LOT-"))
        dlg.close()

        # Backend add_direct_batch also accepts empty/None Lot_Number
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        cursor.lastrowid = 99
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        db.get_raw_connection.return_value = conn

        ib = InventoryBatchManager(db)
        ib.generate_ean13_for_batch = MagicMock(return_value="2000000000991")
        batch_data = {
            "Product_ID": 10,
            "Location_ID": 1,
            "Lot_Number": "",
            "Expiry_Date": None,
            "Quantity": 2,
            "Unit_Price_HT": 1000.0,
        }
        self.assertTrue(ib.add_direct_batch(batch_data, user_id=1))
        self.assertTrue(batch_data["Lot_Number"].startswith("LOT-"))


if __name__ == "__main__":
    unittest.main()
