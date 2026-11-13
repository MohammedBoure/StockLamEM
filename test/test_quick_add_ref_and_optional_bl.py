# -*- coding: utf-8 -*-
"""
test/test_quick_add_ref_and_optional_bl.py
==========================================
Unit tests for Task #6 (Stock & Magasin -> 1. Stock Actuel -> Ajout Rapide):
1. QuickAddDialog product selector displays Réf alongside Product_Name and filters via case-insensitive MatchContains.
2. QuickAddDialog provides an optional N° Bon de Livraison (inp_bl_number) field, pre-fills it in edit mode,
   and returns BL_Number in get_data() without blocking submission when empty.
3. InventoryBatchManager.add_direct_batch persists BL_Number when provided.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from database.inventory_batch_manager import InventoryBatchManager
from ui.widgets.inventory.tabs_batches.quick_add_dialog import QuickAddDialog


class TestQuickAddRefAndOptionalBL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_manager(self):
        mgr = MagicMock()
        mgr.locations = MagicMock()
        mgr.products.get_all_products.return_value = [
            {"Product_ID": 10, "Product_Name": "Réfrigérateur Condor", "Barcode": "REF-CND-1", "Manuf_Name": "Condor", "Stock_Unit": "U"},
            {"Product_ID": 11, "Product_Name": "Réfrigérateur Condor", "Manuf_Cat_No": "REF-CND-2", "Manuf_Name": "Condor", "Stock_Unit": "U"},
        ]
        mgr.db.get_raw_connection.side_effect = Exception("No live DB in unit test")
        return mgr

    def test_product_selector_shows_ref_and_filters_by_name(self):
        mgr = self._make_mock_manager()
        dlg = QuickAddDialog(mgr)

        items = [dlg.cb_product.itemText(i) for i in range(1, dlg.cb_product.count())]
        self.assertEqual(len(items), 2)
        self.assertIn("Réf: REF-CND-1", items[0])
        self.assertIn("Réf: REF-CND-2", items[1])

        completer = dlg.cb_product.completer()
        self.assertEqual(completer.filterMode(), Qt.MatchContains)
        self.assertEqual(completer.caseSensitivity(), Qt.CaseInsensitive)

        completer.setCompletionPrefix("condor")
        matches = [
            completer.completionModel().index(r, 0).data()
            for r in range(completer.completionModel().rowCount())
        ]
        self.assertEqual(len(matches), 2)
        self.assertTrue(any("REF-CND-1" in m for m in matches))
        self.assertTrue(any("REF-CND-2" in m for m in matches))

        dlg.deleteLater()
        self.app.processEvents()

    def test_optional_bl_number_in_quick_add_dialog(self):
        mgr = self._make_mock_manager()
        dlg = QuickAddDialog(mgr)

        self.assertTrue(hasattr(dlg, "inp_bl_number"))
        dlg.cb_product.setCurrentIndex(1)
        dlg.cb_location.get_current_location_id = MagicMock(return_value=1)
        dlg.cb_supplier.addItem("Fournisseur Test", 5)
        dlg.cb_supplier.setCurrentIndex(1)
        dlg.inp_lot.setText("LOT-100")
        dlg.inp_qty.setValue(3)
        dlg.inp_price.setValue(25000.0)
        dlg.inp_sell_price.setValue(30000.0)

        # Optional: empty BL still validates and returns ''
        dlg.inp_bl_number.setText("")
        with patch.object(QMessageBox, "warning", side_effect=AssertionError("Unexpected warning")):
            dlg.validate_and_accept()
        self.assertEqual(dlg.get_data()["BL_Number"], "")

        # Filled BL is returned
        dlg.inp_bl_number.setText("BL-2026-099")
        self.assertEqual(dlg.get_data()["BL_Number"], "BL-2026-099")

        dlg.deleteLater()
        self.app.processEvents()

    def test_prefill_bl_number_in_edit_mode(self):
        mgr = self._make_mock_manager()
        batch_data = {
            "Batch_ID": 55,
            "Product_ID": 10,
            "Location_ID": 1,
            "Quantity_Initial": 4,
            "Lot_Number": "LOT-55",
            "Unit_Price_Received": 15000.0,
            "Selling_Price_HT": 19000.0,
            "BL_Number": "BL-EDIT-55",
        }
        dlg = QuickAddDialog(mgr, batch_data=batch_data)
        self.assertEqual(dlg.inp_bl_number.text(), "BL-EDIT-55")

        dlg.deleteLater()
        self.app.processEvents()

    def test_add_direct_batch_persists_bl_number(self):
        fake_cursor = MagicMock()
        fake_cursor.lastrowid = 123
        fake_cursor.fetchone.return_value = ("BL_Number",)

        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor

        fake_db = MagicMock()
        fake_db.get_raw_connection.return_value = fake_conn

        batch_mgr = InventoryBatchManager(fake_db)
        batch_mgr.generate_ean13_for_batch = MagicMock(return_value="2000000001234")

        ok = batch_mgr.add_direct_batch({
            "Product_ID": 10,
            "Location_ID": 1,
            "Lot_Number": "LOT-10",
            "Expiry_Date": None,
            "Quantity": 2,
            "Unit_Price_HT": 10000.0,
            "BL_Number": "BL-2026-777",
        })
        self.assertTrue(ok)

        bl_updates = [
            c for c in fake_cursor.execute.call_args_list
            if "SET BL_Number = %s" in c[0][0]
        ]
        self.assertEqual(len(bl_updates), 1)
        self.assertEqual(bl_updates[0][0][1], ("BL-2026-777", 123))


if __name__ == "__main__":
    unittest.main()
